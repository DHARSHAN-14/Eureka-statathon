// Redirect to login on any 401 from admin APIs
      const _origFetch = window.fetch;
      window.fetch = async function(...args) {
        const response = await _origFetch(...args);
        if (response.status === 401) {
          const url = typeof args[0] === 'string' ? args[0] : (args[0]?.url || '');
          if (url.includes('/admin/')) {
            window.location.href = '/admin/login';
          }
        }
        return response;
      };

      // Global chart instances (charts removed from UI)
      window.charts = {};
      let refreshInterval;
      window.analyticsLoading = false;
      const ANALYTICS_REFRESH_MS = 300000; // 5 min — reduces server load on low-end deployments
      const ANALYTICS_HISTORY_LIMIT = 5000;
      let occupationsLoadPromise = null;

      // Global variables
      let occupations = [];
      let filteredOccupations = [];
      let currentPage = 1;
      const recordsPerPage = 25;

      let currentHistoryOccupationTitle = "";
      let currentHistoryRows = [];
      let currentSearchTerm = "";
      let semanticSearchResults = [];
      let semanticSearchTimer = null;
      let semanticSearchRequestId = 0;
      let allAnalyticsHistory = [];
      let analyticsControlTimer = null;
      const charts = window.charts;

      // Move all modals to body immediately to prevent z-index backdrop issues
      document.querySelectorAll('.modal').forEach(modal => {
        document.body.appendChild(modal);
      });

      // Initialize dashboard on page load
      let dashboardInitialized = false;
      document.addEventListener("DOMContentLoaded", function () {
        initializeDashboard();
      });

      // Fallback in case DOMContentLoaded already fired
      if (document.readyState === "complete" || document.readyState === "interactive") {
        setTimeout(initializeDashboard, 1);
      }

      function initializeDashboard() {
        if (dashboardInitialized) return;
        dashboardInitialized = true;
        
        initializeCharts();
        loadAnalyticsData();
        updateLastUpdateTime();
        startAnalyticsAutoRefresh();
        
        // Silently load occupations in the background so NCO charts get their division data
        ensureOccupationsLoaded().catch(e => console.warn("Background occupations load failed:", e));
      }

      function startAnalyticsAutoRefresh() {
        if (refreshInterval) {
          clearInterval(refreshInterval);
          refreshInterval = null;
        }

        refreshInterval = setInterval(() => {
          if (document.hidden) {
            return;
          }
          const analyticsTab = document.getElementById('analytics-tab');
          const ncoTab = document.getElementById('nco-analysis-tab');
          if (analyticsTab?.classList.contains('active')) {
            loadAnalyticsData();
          } else if (ncoTab?.classList.contains('active')) {
            loadNcoAnalysisData();
          }
        }, ANALYTICS_REFRESH_MS);
      }

      // Loading functions
      function showLoading() {
        document.getElementById('loadingOverlay').style.display = 'flex';
      }

      function hideLoading() {
        document.getElementById('loadingOverlay').style.display = 'none';
      }

      // Data loading functions
      function ensureOccupationsLoaded() {
        if (occupations.length > 0) {
          return Promise.resolve(occupations);
        }
        if (occupationsLoadPromise) {
          return occupationsLoadPromise;
        }
        occupationsLoadPromise = loadOccupations({ silent: true });
        return occupationsLoadPromise;
      }

      function loadOccupations(options = {}) {
        const silent = Boolean(options.silent);
        if (!silent) {
          showLoading();
        }

        const promise = fetch("/admin/api/occupations")
          .then((response) => response.json())
          .then((data) => {
            occupations = Array.isArray(data) ? data : [];
            filteredOccupations = [...occupations];
            _ncoLookupMap = null; // invalidate lookup cache so it rebuilds with fresh data

            if (!silent) {
              updateStatistics();
              updateFilters();
              displayTable();
            } else {
              updateFilters();
            }

            if (allAnalyticsHistory.length) {
              updateSearchAnalyticsCharts(allAnalyticsHistory);
            }
            return occupations;
          })
          .catch((error) => {
            console.error("Error loading occupations:", error);
            if (!silent) {
              showNotification("Failed to load occupations data", "error");
            }
            throw error;
          })
          .finally(() => {
            if (!silent) {
              hideLoading();
            }
          });

        occupationsLoadPromise = promise;
        return promise;
      }

      function loadNcoAnalysisData() {
        initIndiaMap();
      }

      function updateStatistics() {
        const totalOccupationsEl = document.getElementById("totalOccupations");
        if (totalOccupationsEl) {
          totalOccupationsEl.textContent = occupations.length.toLocaleString();
        }

        const divisions = new Set(occupations.map((occ) => occ.division).filter((d) => d));
        const totalDivisionsEl = document.getElementById("totalDivisions");
        if (totalDivisionsEl) {
          totalDivisionsEl.textContent = divisions.size.toLocaleString();
        }

        const families = new Set(occupations.map((occ) => occ.family).filter((f) => f));
        const totalFamiliesEl = document.getElementById("totalFamilies");
        if (totalFamiliesEl) {
          totalFamiliesEl.textContent = families.size.toLocaleString();
        }

        // Calculate data completeness
        const totalFields = occupations.length * 8; // Approximate fields per record
        const filledFields = occupations.reduce((count, occ) => {
          return count + [
            occ.occupation_title,
            occ.nco_code,
            occ.division,
            occ.family,
            occ.description,
            occ.nco_2004_code
          ].filter(field => field && field.trim()).length;
        }, 0);
        const completeness = totalFields > 0 ? Math.round((filledFields / totalFields) * 100) : 0;
        const dataCompletenessEl = document.getElementById("dataCompleteness");
        if (dataCompletenessEl) {
          dataCompletenessEl.textContent = completeness + '%';
        }
      }

      
      // Chart initialization - Create all 6 Chart.js instances
      function initializeCharts() {
        if (typeof Chart !== "undefined") {
          Chart.defaults.animation = false;
        }
        // 1. Search Volume Trend Chart
        const ctxVolume = document.getElementById('searchVolumeTrendChart');
        if (ctxVolume && !charts.searchVolumeTrendChart) {
          charts.searchVolumeTrendChart = new Chart(ctxVolume, {
            type: 'line',
            data: {
              labels: [],
              datasets: [{
                label: 'Searches',
                data: [],
                borderColor: '#0b3d91',
                backgroundColor: 'rgba(11, 61, 145, 0.05)',
                borderWidth: 2,
                tension: 0.4,
                fill: true,
                pointBackgroundColor: '#0b3d91',
                pointBorderColor: '#fff',
                pointBorderWidth: 2,
                pointRadius: 5
              }]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              plugins: {
                legend: { display: false }
              },
              scales: {
                y: {
                  beginAtZero: true,
                  ticks: { stepSize: 1, color: '#6b7280' },
                  grid: { color: '#e5e7eb' }
                },
                x: {
                  ticks: { color: '#6b7280' },
                  grid: { display: false }
                }
              }
            }
          });
        }

        // 2. Top 10 Searches Chart
        const ctxTopSearches = document.getElementById('topSearchesChart');
        if (ctxTopSearches && !charts.topSearchesChart) {
          charts.topSearchesChart = new Chart(ctxTopSearches, {
            type: 'bar',
            data: {
              labels: [],
              datasets: [{
                label: 'Search Count',
                data: [],
                backgroundColor: '#f97316',
                borderColor: '#ea580c',
                borderWidth: 1
              }]
            },
            options: {
              indexAxis: 'y',
              responsive: true,
              maintainAspectRatio: false,
              plugins: {
                legend: { display: false }
              },
              scales: {
                x: {
                  beginAtZero: true,
                  ticks: { stepSize: 1, color: '#6b7280' },
                  grid: { color: '#e5e7eb' }
                },
                y: {
                  ticks: { color: '#6b7280' },
                  grid: { display: false }
                }
              }
            }
          });
        }

        // 3. Search Success Rate Chart replaced by D3 Sunburst chart

        // 4. Language Distribution Chart
        const ctxLanguage = document.getElementById('languageDistributionChart');
        if (ctxLanguage && !charts.languageDistributionChart) {
          charts.languageDistributionChart = new Chart(ctxLanguage, {
            type: 'pie',
            data: {
              labels: [],
              datasets: [{
                data: [],
                backgroundColor: [
                  '#1e3a8a', '#3b82f6', '#60a5fa', '#93c5fd', '#dbeafe',
                  '#f97316', '#fed7aa', '#10b981', '#6ee7b7', '#a7f3d0'
                ],
                borderColor: '#fff',
                borderWidth: 2
              }]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              plugins: {
                legend: { position: 'bottom', labels: { color: '#6b7280' } }
              }
            }
          });
        }

        // 5. Top 10 Occupations Chart
        const ctxOccupations = document.getElementById('topOccupationsChart');
        if (ctxOccupations && !charts.topOccupationsChart) {
          charts.topOccupationsChart = new Chart(ctxOccupations, {
            type: 'bar',
            data: {
              labels: [],
              datasets: [{
                label: 'Found Count',
                data: [],
                backgroundColor: '#3b82f6',
                borderColor: '#1e40af',
                borderWidth: 1
              }]
            },
            options: {
              indexAxis: 'y',
              responsive: true,
              maintainAspectRatio: false,
              plugins: {
                legend: { display: false }
              },
              scales: {
                x: {
                  beginAtZero: true,
                  ticks: { stepSize: 1, color: '#6b7280' },
                  grid: { color: '#e5e7eb' }
                },
                y: {
                  ticks: { color: '#6b7280' },
                  grid: { display: false }
                }
              }
            }
          });
        }

        // 6. NCO Division Demand Chart
        const ctxConfidence = document.getElementById('confidenceTrendChart');
        if (ctxConfidence && !charts.confidenceTrendChart) {
          charts.confidenceTrendChart = new Chart(ctxConfidence, {
            type: 'bar',
            data: {
              labels: [],
              datasets: [{
                label: 'Search Matches',
                data: [],
                backgroundColor: '#10b981',
                borderColor: '#047857',
                borderWidth: 1
              }]
            },
            options: {
              indexAxis: 'y',
              responsive: true,
              maintainAspectRatio: false,
              plugins: {
                legend: { display: false }
              },
              scales: {
                x: {
                  beginAtZero: true,
                  ticks: { stepSize: 1, color: '#6b7280' },
                  grid: { color: '#e5e7eb' }
                },
                y: {
                  ticks: { color: '#6b7280' },
                  grid: { display: false }
                }
              }
            }
          });
        }

      }

      function updateChartsData() {
        return;
      }

      // Cache for nco_code → occupation lookup (built once, reused on every chart update)
      let _ncoLookupMap = null;

      function _buildNcoLookup() {
        if (_ncoLookupMap) return _ncoLookupMap;
        _ncoLookupMap = new Map();
        (occupations || []).forEach(occ => {
          if (occ.nco_code) _ncoLookupMap.set(String(occ.nco_code).trim(), occ);
        });
        return _ncoLookupMap;
      }

      /**
       * Looks up a hierarchy property (division / sub_division / group / family)
       * for a prompt_history entry using its nco_code.
       */
      function getAnalyticsEntryProperty(entry, field) {
        if (!entry) return null;
        // Direct field on entry (e.g. already enriched)
        if (entry[field]) return entry[field];
        // Look up via nco_code
        const code = entry.nco_code || entry.nco2015_code || '';
        if (!code) return null;
        const lookup = _buildNcoLookup();
        const occ = lookup.get(String(code).trim());
        return occ ? (occ[field] || null) : null;
      }


      function updateSearchAnalyticsCharts(historyData) {
        if (!Array.isArray(historyData)) {
          console.warn("Invalid history data");
          return;
        }

        allAnalyticsHistory = historyData;

        if (historyData.length > 0) {
          const dates = historyData.map(entry => parseAnalyticsDate(entry.ts)).filter(Boolean);
          if (dates.length > 0) {
            const minDate = new Date(Math.min(...dates));
            const maxDate = new Date();
            
            const minDateStr = minDate.toISOString().split('T')[0];
            const maxDateStr = maxDate.toISOString().split('T')[0];
            
            const startInput = document.getElementById("analyticsStartDate");
            const endInput = document.getElementById("analyticsEndDate");
            
            if (startInput) {
              startInput.min = minDateStr;
              startInput.max = maxDateStr;
              if (!startInput.value) startInput.value = minDateStr;
            }
            if (endInput) {
              endInput.min = minDateStr;
              endInput.max = maxDateStr;
              if (!endInput.value) endInput.value = maxDateStr;
            }
          }
        }

        populateAnalyticsFilterOptions();
        const filteredHistory = getFilteredAnalyticsHistory(historyData);
        
        // Calculate max range based on available distinct values
        const uniqueQueries = new Set(filteredHistory.map(entry => entry.query).filter(Boolean)).size;
        const uniqueOccups = new Set(filteredHistory.map(entry => entry.occupation_title).filter(Boolean)).size;
        const uniqueDivs = new Set(filteredHistory.map(entry => getAnalyticsEntryProperty(entry, 'division')).filter(Boolean)).size;
        
        // Set dynamic max limit for the slider based on the data length
        const maxRange = Math.max(5, uniqueQueries, uniqueOccups, uniqueDivs);
        
        const topNInput = document.getElementById("analyticsTopN");
        if (topNInput) {
          topNInput.max = maxRange;
          // Enforce bounds immediately if current value exceeds new max
          if (parseInt(topNInput.value, 10) > maxRange) {
            topNInput.value = maxRange;
          }
          const valEl = document.getElementById("analyticsTopNValue");
          if (valEl) valEl.textContent = topNInput.value;
        }

        const topN = getAnalyticsTopN();
        const groupBy = document.getElementById("analyticsGroupBy")?.value || "day";

        updateAnalyticsMetricTiles(filteredHistory);

        // ===== CHART 1: Search Volume Trend =====
        const trendCounts = countByTimeBucket(filteredHistory, groupBy);
        const trendEntries = Object.entries(trendCounts);

        if (charts.searchVolumeTrendChart) {
          charts.searchVolumeTrendChart.data.labels = trendEntries.map(([label]) => label);
          charts.searchVolumeTrendChart.data.datasets[0].data = trendEntries.map(([, count]) => count);
          charts.searchVolumeTrendChart.update("none");
        }
        setTextContent("searchVolumeTrendTitle", `Search Volume Trend by ${capitalize(groupBy)}`);

        // ===== CHART 2: Top Search Queries =====
        const topSearches = topCounts(filteredHistory, (entry) => entry.query, topN);

        if (charts.topSearchesChart) {
          charts.topSearchesChart.data.labels = topSearches.map(([query]) => truncateLabel(query, 35));
          charts.topSearchesChart.data.datasets[0].data = topSearches.map(([, count]) => count);
          charts.topSearchesChart.update("none");
        }
        setTextContent("topSearchesTitle", `Top ${topN} Search Queries`);

        // ===== CHART 3: NCO Search Demand Sunburst =====
        drawNcoSearchDemandSunburst(filteredHistory);

        // ===== CHART 4: Translation Usage =====
        const languageCounts = {};
        filteredHistory.forEach(entry => {
          let langName = entry.detected_language;
          if (!langName) {
            if (entry.was_translated) {
              langName = "Tamil";
            } else {
              langName = "English";
            }
          }
          if (langName === "en" || langName === "English") langName = "English";
          
          languageCounts[langName] = (languageCounts[langName] || 0) + 1;
        });

        const languageColors = {
          "English": "#5dade2",      // Soft Sapphire Blue
          "Tamil": "#ec7063",        // Pastel Coral / Rose
          "Hindi": "#f4d03f",        // Pastel Gold
          "Telugu": "#eb984e",       // Pastel Orange
          "Bengali": "#af7ac5",      // Pastel Amethyst
          "Marathi": "#52be80",      // Sage Green
          "Gujarati": "#a569bd",     // Pastel Orchid
          "Kannada": "#48c9b0",      // Pastel Mint
          "Malayalam": "#58d68d",    // Pastel Light Green
          "Punjabi": "#f5b041",      // Pastel Amber
          "Urdu": "#85c1e9",         // Pastel Sky Blue
          "Other": "#cbd5e1"         // Soft Gray
        };

        if (charts.languageDistributionChart) {
          const labels = Object.keys(languageCounts);
          const data = Object.values(languageCounts);
          const bgColors = labels.map(lang => languageColors[lang] || languageColors["Other"]);
          
          charts.languageDistributionChart.data.labels = labels;
          charts.languageDistributionChart.data.datasets[0].data = data;
          charts.languageDistributionChart.data.datasets[0].backgroundColor = bgColors;
          charts.languageDistributionChart.update("none");
        }

        // ===== CHART 5: Top Matched Occupations =====
        const topOccupations = topCounts(filteredHistory, (entry) => entry.occupation_title, topN);

        if (charts.topOccupationsChart) {
          charts.topOccupationsChart.data.labels = topOccupations.map(([title]) => truncateLabel(title, 35));
          charts.topOccupationsChart.data.datasets[0].data = topOccupations.map(([, count]) => count);
          charts.topOccupationsChart.update("none");
        }
        setTextContent("topOccupationsTitle", `Top ${topN} Matched Occupations`);

        // ===== CHART 6: NCO Division Demand =====
        const topDivisions = topCounts(filteredHistory, (entry) => getAnalyticsEntryProperty(entry, 'division'), topN);

        if (charts.confidenceTrendChart) {
          charts.confidenceTrendChart.data.labels = topDivisions.map(([division]) => truncateLabel(division, 35));
          charts.confidenceTrendChart.data.datasets[0].data = topDivisions.map(([, count]) => count);
          charts.confidenceTrendChart.update("none");
        }

        // Update last update time
        updateLastUpdateTime();
      }

      const ncoColorScale = d3.scaleOrdinal(d3.schemeCategory10);

      function lookupNcoHierarchyMeta(categoryName, level, sampleNcoCode = "") {
        const descFieldMap = {
          division: "division_description",
          sub_division: "sub_division_description",
          group: "group_description",
          family: "family_description",
        };
        const fieldMap = {
          division: "division",
          sub_division: "sub_division",
          group: "group",
          family: "family",
        };

        const field = fieldMap[level];
        const occ = (occupations || []).find((item) => item[field] === categoryName);
        const ncoCode = sampleNcoCode || occ?.nco_code || "";
        let code = "";

        if (ncoCode) {
          const base = String(ncoCode).split(".")[0];
          if (level === "division") code = base.substring(0, 1);
          else if (level === "sub_division") code = base.substring(0, 2);
          else if (level === "group") code = base.substring(0, 3);
          else code = base;
        }

        return {
          code,
          description: occ ? (occ[descFieldMap[level]] || "") : "",
        };
      }

      function drawNcoSearchDemandSunburst(historyData) {
        const container = document.getElementById("sunburstChartContainer");
        if (!container) return;

        // 1. Clear previous chart
        d3.select(container).selectAll("*").remove();

        // 2. Build hierarchical data (now including 4 levels: Division -> Sub-Division -> Group -> Family)
        const rootData = { name: "NCO", children: [] };
        
        historyData.forEach(entry => {
          const div = getAnalyticsEntryProperty(entry, "division");
          const sub = getAnalyticsEntryProperty(entry, "sub_division");
          const grp = getAnalyticsEntryProperty(entry, "group");
          const fam = getAnalyticsEntryProperty(entry, "family");

          if (!div) return;

          // Find/create Division
          let divNode = rootData.children.find(c => c.name === div);
          if (!divNode) {
            divNode = { name: div, children: [] };
            rootData.children.push(divNode);
          }

          if (!sub) return;

          // Find/create Sub-Division
          let subNode = divNode.children.find(c => c.name === sub);
          if (!subNode) {
            subNode = { name: sub, children: [] };
            divNode.children.push(subNode);
          }

          if (!grp) return;

          // Find/create Group
          let grpNode = subNode.children.find(c => c.name === grp);
          if (!grpNode) {
            grpNode = { name: grp, children: [] };
            subNode.children.push(grpNode);
          }

          if (!fam) return;

          // Find/create Family
          let famNode = grpNode.children.find(c => c.name === fam);
          if (!famNode) {
            famNode = { name: fam, value: 0 };
            grpNode.children.push(famNode);
          }

          famNode.value += 1;
        });

        // Compute total values bottom-up before grouping
        function computeNodeValues(node) {
          if (node.children && node.children.length > 0) {
            node.value = node.children.reduce((sum, child) => sum + computeNodeValues(child), 0);
          }
          return node.value || 0;
        }
        computeNodeValues(rootData);

        // Group tiny slivers into "Other" so slices are ALWAYS large and clickable
        function groupTinySlices(node, maxChildren) {
          if (!node.children || node.children.length === 0) return;
          
          if (node.children.length > maxChildren) {
            node.children.sort((a, b) => b.value - a.value);
            const top = node.children.slice(0, maxChildren - 1);
            const rest = node.children.slice(maxChildren - 1);
            
            const otherValue = rest.reduce((sum, c) => sum + c.value, 0);
            
            top.push({
              name: `Other (${rest.length} smaller)`,
              value: otherValue,
              children: [] // Truncate deeper levels for 'Other' to prevent clutter
            });
            
            node.children = top;
          }
          
          node.children.forEach(c => groupTinySlices(c, maxChildren));
        }
        
        // Keep top 7 slices per parent, group the rest into "Other"
        groupTinySlices(rootData, 8);

        // If there are no valid children, display "No Data" message
        if (rootData.children.length === 0) {
          d3.select(container).append("div")
            .style("color", "#94a3b8")
            .style("font-size", "14px")
            .style("font-style", "italic")
            .text("No NCO-mapped queries found in history.");
          return;
        }

        // 3. Set up dimensions
        const width = container.clientWidth || 280;
        const height = container.clientHeight || 280;
        const radius = Math.min(width, height) / 2;

        // 4. Create SVG
        const svg = d3.select(container)
          .append("svg")
          .attr("width", width)
          .attr("height", height)
          .append("g")
          .attr("transform", `translate(${width / 2}, ${height / 2})`);

        // 5. Partition layout
        const hierarchy = d3.hierarchy(rootData)
          .sum(d => (d.children && d.children.length > 0) ? 0 : d.value)
          .sort((a, b) => b.value - a.value);

        const partition = d3.partition()
          .size([2 * Math.PI, hierarchy.height + 1]);

        const root = partition(hierarchy);
        root.each(d => {
          d.current = { x0: d.x0, x1: d.x1, y0: d.depth, y1: d.depth + 1 };
          d.target = { x0: d.x0, x1: d.x1, y0: d.depth, y1: d.depth + 1 };
        });

        // 6. Arc generator
        const centerRadius = 45;
        const ringWidth = (radius - centerRadius) / 4;

        const arc = d3.arc()
          .startAngle(d => d.x0)
          .endAngle(d => d.x1)
          .padAngle(d => Math.min((d.x1 - d.x0) / 2, 0.01))
          .padRadius(radius / 2)
          .innerRadius(d => Math.max(0, centerRadius + (d.y0 - 1) * ringWidth))
          .outerRadius(d => Math.max(0, centerRadius + d.y0 * ringWidth - 2));

        // 7. Colors
        const divisionColors = {
          "Managers": "#5dade2",
          "Professionals": "#af7ac5",
          "Technicians and Associate Professionals": "#48c9b0",
          "Clerks/Clerical Support Workers": "#52be80",
          "Service and Sales Workers": "#f4d03f",
          "Skilled Agricultural, Forestry and Fishery Workers": "#eb984e",
          "Craft and Related Trades Workers": "#ec7063",
          "Plant and Machine Operators, and Assemblers": "#a569bd",
          "Elementary Occupations": "#a6acaf"
        };

        function getNodeColor(d) {
          if (d.depth === 0) return "#ffffff";
          let p = d;
          while (p.depth > 1) p = p.parent;
          const divisionName = p.data.name;
          const hexColor = divisionColors[divisionName] || ncoColorScale(divisionName) || "#cbd5e1";
          const baseColor = d3.color(hexColor);
          if (d.depth === 1) return baseColor.toString();
          if (d.depth === 2) return baseColor.brighter(0.22).toString();
          if (d.depth === 3) return baseColor.brighter(0.44).toString();
          return baseColor.brighter(0.66).toString();
        }

        // State for zooming
        let zoomedNode = root;

        // 8. Render paths
        const paths = svg.selectAll("path")
          .data(root.descendants().filter(d => d.depth > 0))
          .enter()
          .append("path")
          .attr("d", d => arc(d.current))
          .style("fill", d => getNodeColor(d))
          .style("stroke", "#ffffff")
          .style("stroke-width", "1px")
          .style("cursor", "pointer")
          .on("click", clicked);

        function clicked(event, p) {
          if (!p) return;
          zoomedNode = p;

          const t = svg.transition().duration(750);

          root.each(d => {
            let t_x0, t_x1;
            if (p.depth === 0) {
              t_x0 = d.x0;
              t_x1 = d.x1;
            } else {
              t_x0 = Math.max(0, Math.min(1, (d.x0 - p.x0) / (p.x1 - p.x0))) * 2 * Math.PI;
              t_x1 = Math.max(0, Math.min(1, (d.x1 - p.x0) / (p.x1 - p.x0))) * 2 * Math.PI;
            }
            d.target = { x0: t_x0, x1: t_x1, y0: d.depth, y1: d.depth + 1 };
          });

          paths.transition(t)
            .tween("data", d => {
              const i = d3.interpolate(d.current, d.target);
              return t => d.current = i(t);
            })
            .style("display", d => (d.target.x1 - d.target.x0) < 0.005 ? "none" : "block")
            .attrTween("d", d => () => arc(d.current));
            
          d3.select(".sunburst-center-value").text(p.value.toLocaleString());
          d3.select(".sunburst-center-label")
            .text(p.depth === 0 ? "Total Searches" : "Click to Reset")
            .style("fill", p.depth === 0 ? "#64748b" : "#0284c7")
            .style("cursor", p.depth === 0 ? "default" : "pointer");
        }

        // 9. Tooltip logic
        const activeInfo = document.getElementById("sunburstActiveInfo");

        paths.on("mouseover", function(event, d) {
          paths.style("opacity", node => node.style && node.style.display === "none" ? 0 : 0.35);
          
          const ancestorsNodes = [];
          let current = d;
          while (current.depth > 0) {
            ancestorsNodes.push(current);
            current = current.parent;
          }
          paths.filter(node => ancestorsNodes.includes(node))
            .style("opacity", 1.0)
            .style("stroke", "#334155")
            .style("stroke-width", "1.5px");

          const totalSearches = root.value || 1;
          const share = ((d.value / totalSearches) * 100).toFixed(1);
          
          let levelLabel = "Division";
          if (d.depth === 2) levelLabel = "Sub-Division";
          if (d.depth === 3) levelLabel = "Group";
          if (d.depth === 4) levelLabel = "Family";

          const meta = lookupNcoHierarchyMeta(
            d.data.name, 
            d.depth === 1 ? 'division' : 
            d.depth === 2 ? 'sub_division' : 
            d.depth === 3 ? 'group' : 'family'
          );
          const codePrefix = meta && meta.code ? `[Code ${meta.code}] ` : "";

          let displayName = d.data.name;
          if (displayName.includes(":")) {
            displayName = displayName.split(":").slice(1).join(":").trim();
          }

          if (activeInfo) {
            activeInfo.innerHTML = `
              <div style="display: flex; flex-direction: column; align-items: center; gap: 3px; width: 100%;">
                <div style="font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px;">
                  ${levelLabel}
                </div>
                <div style="font-size: 12px; font-weight: 700; color: #0f172a; text-align: center; line-height: 1.3;">
                  ${codePrefix}${displayName}
                </div>
                <div style="font-size: 12px; font-weight: 600; color: #0284c7; background: #e0f2fe; padding: 2px 8px; border-radius: 12px; margin-top: 2px;">
                  ${d.value.toLocaleString()} search${d.value === 1 ? "" : "es"} (${share}%)
                </div>
              </div>
            `;
          }

          d3.select(".sunburst-center-value").text(d.value.toLocaleString());
        })
        .on("mouseleave", function() {
          paths.style("opacity", 1.0)
            .style("stroke", "#ffffff")
            .style("stroke-width", "1px");

          if (activeInfo) {
            activeInfo.textContent = "Hover over a segment to view NCO classification details";
          }

          d3.select(".sunburst-center-value").text(zoomedNode.value.toLocaleString());
        });

        // 10. Center circle (Zoom Reset)
        const centerCircle = svg.append("circle")
          .attr("r", centerRadius + 2)
          .style("fill", "#ffffff")
          .style("stroke", "#e2e8f0")
          .style("stroke-width", "1px")
          .style("cursor", "pointer")
          .on("click", (event) => clicked(event, root));

        const centerTextG = svg.append("g").style("pointer-events", "none");

        centerTextG.append("text")
          .attr("class", "sunburst-center-value")
          .attr("y", -2)
          .attr("text-anchor", "middle")
          .style("font-size", "18px")
          .style("font-weight", "800")
          .style("fill", "#0f172a")
          .style("font-family", "Arial, sans-serif")
          .text(root.value.toLocaleString());

        centerTextG.append("text")
          .attr("class", "sunburst-center-label")
          .attr("y", 16)
          .attr("text-anchor", "middle")
          .style("font-size", "10px")
          .style("font-weight", "600")
          .style("fill", "#64748b")
          .style("font-family", "Arial, sans-serif")
          .text("Total Searches");
      }

      function applyAnalyticsControls() {
        clearTimeout(analyticsControlTimer);
        analyticsControlTimer = setTimeout(() => {
          updateSearchAnalyticsCharts(allAnalyticsHistory);
        }, 120);
      }

      function resetAnalyticsControls() {
        setControlValue("analyticsDateRange", "all");
        setControlValue("analyticsStartDate", "");
        setControlValue("analyticsEndDate", "");
        setControlValue("analyticsGroupBy", "day");
        setControlValue("analyticsQueryFilter", "");
        setControlValue("analyticsOccupationFilter", "");
        setControlValue("analyticsDivisionFilter", "");
        setControlValue("analyticsSubDivisionFilter", "");
        setControlValue("analyticsGroupFilter", "");
        setControlValue("analyticsOutcomeFilter", "");
        setControlValue("analyticsTopN", "10");
        updateSearchAnalyticsCharts(allAnalyticsHistory);
      }

      function getFilteredAnalyticsHistory(historyData) {
        const dateRange = document.getElementById("analyticsDateRange")?.value || "all";
        const dateWindow = getAnalyticsDateWindow(dateRange);
        const queryFilter = (document.getElementById("analyticsQueryFilter")?.value || "").trim().toLowerCase();
        const occupationFilter = document.getElementById("analyticsOccupationFilter")?.value || "";
        const divisionFilter = document.getElementById("analyticsDivisionFilter")?.value || "";
        const subDivisionFilter = document.getElementById("analyticsSubDivisionFilter")?.value || "";
        const groupFilter = document.getElementById("analyticsGroupFilter")?.value || "";
        const outcomeFilter = document.getElementById("analyticsOutcomeFilter")?.value || "";

        return historyData.filter((entry) => {
          const entryDate = parseAnalyticsDate(entry.ts);
          if (!entryDate) return false;
          if (dateWindow.start && entryDate < dateWindow.start) return false;
          if (dateWindow.end && entryDate > dateWindow.end) return false;
          if (queryFilter && !`${entry.query || ""} ${entry.translated_query || ""}`.toLowerCase().includes(queryFilter)) return false;
          if (occupationFilter && (entry.occupation_title || "") !== occupationFilter) return false;
          if (divisionFilter && getAnalyticsEntryProperty(entry, 'division') !== divisionFilter) return false;
          if (subDivisionFilter && getAnalyticsEntryProperty(entry, 'sub_division') !== subDivisionFilter) return false;
          if (groupFilter && getAnalyticsEntryProperty(entry, 'group') !== groupFilter) return false;
          if (outcomeFilter === "success" && !isSuccessfulAnalyticsEntry(entry)) return false;
          if (outcomeFilter === "empty" && isSuccessfulAnalyticsEntry(entry)) return false;
          if (outcomeFilter === "translated" && !entry.was_translated) return false;
          if (outcomeFilter === "original" && entry.was_translated) return false;
          return true;
        });
      }

      function getAnalyticsDateWindow(dateRange) {
        if (dateRange === "all") return { start: null, end: null };

        if (dateRange === "custom") {
          const startValue = document.getElementById("analyticsStartDate")?.value;
          const endValue = document.getElementById("analyticsEndDate")?.value;
          const start = startValue ? new Date(`${startValue}T00:00:00`) : null;
          const end = endValue ? new Date(`${endValue}T23:59:59`) : null;
          return { start, end };
        }

        const days = parseInt(dateRange, 10) || 7;
        const end = new Date();
        const start = new Date();
        start.setDate(end.getDate() - (days - 1));
        start.setHours(0, 0, 0, 0);
        end.setHours(23, 59, 59, 999);
        return { start, end };
      }

      function populateAnalyticsFilterOptions() {
        populateAnalyticsSelect(
          "analyticsOccupationFilter",
          "All occupations",
          [...new Set(allAnalyticsHistory.map((entry) => entry.occupation_title).filter(Boolean))].sort()
        );

        const divisions = [...new Set(
          allAnalyticsHistory
            .map((entry) => getAnalyticsEntryProperty(entry, 'division'))
            .filter(Boolean)
        )].sort();
        populateAnalyticsSelect("analyticsDivisionFilter", "All divisions", divisions);

        const subDivisions = [...new Set(
          allAnalyticsHistory
            .map((entry) => getAnalyticsEntryProperty(entry, 'sub_division'))
            .filter(Boolean)
        )].sort();
        populateAnalyticsSelect("analyticsSubDivisionFilter", "All sub-divisions", subDivisions);

        const groups = [...new Set(
          allAnalyticsHistory
            .map((entry) => getAnalyticsEntryProperty(entry, 'group'))
            .filter(Boolean)
        )].sort();
        populateAnalyticsSelect("analyticsGroupFilter", "All groups", groups);
      }

      function populateAnalyticsSelect(selectId, allLabel, values) {
        const select = document.getElementById(selectId);
        if (!select) return;
        const currentValue = select.value;
        select.innerHTML = "";
        select.appendChild(new Option(allLabel, ""));
        values.forEach((value) => select.appendChild(new Option(value, value)));
        if (values.includes(currentValue)) {
          select.value = currentValue;
        }
      }

      function updateAnalyticsMetricTiles(filteredHistory) {
        const total = filteredHistory.length;
        
        let totalConfidence = 0;
        let validScores = 0;
        
        filteredHistory.forEach(entry => {
          if (isSuccessfulAnalyticsEntry(entry) && entry.occupation_title) {
            const q = (entry.translated_query || entry.query || "").toLowerCase();
            const t = entry.occupation_title.toLowerCase();
            let score = 0;
            if (t === q) {
              score = 100;
            } else if (t.includes(q) || q.includes(t)) {
              score = 90;
            } else if (q && t) {
              const words = q.split(/\s+/).filter(w => w.length > 2);
              const matches = words.filter(w => t.includes(w)).length;
              score = words.length ? 60 + (matches / words.length) * 30 : 60;
            } else {
              score = 50;
            }
            totalConfidence += score;
            validScores++;
          }
        });
        
        const avgConfidence = validScores > 0 ? (totalConfidence / validScores).toFixed(1) : "0.0";
        const translatedCount = filteredHistory.filter((entry) => entry.was_translated).length;
        const uniqueOccupations = new Set(filteredHistory.map((entry) => entry.occupation_title).filter(Boolean)).size;

        setTextContent("analyticsMetricSearches", total.toLocaleString());
        setTextContent("analyticsMetricConfidence", `${avgConfidence}%`);
        setTextContent("analyticsMetricTranslated", total ? `${((translatedCount / total) * 100).toFixed(1)}%` : "0%");
        setTextContent("analyticsMetricOccupations", uniqueOccupations.toLocaleString());
      }

      function countByTimeBucket(historyData, groupBy) {
        const counts = {};
        historyData
          .slice()
          .sort((a, b) => parseAnalyticsDate(a.ts) - parseAnalyticsDate(b.ts))
          .forEach((entry) => {
            const date = parseAnalyticsDate(entry.ts);
            if (!date) return;
            const label = getTimeBucketLabel(date, groupBy);
            counts[label] = (counts[label] || 0) + 1;
          });
        return counts;
      }

      function getTimeBucketLabel(date, groupBy) {
        if (groupBy === "month") {
          return date.toLocaleDateString("en-US", { month: "short", year: "2-digit" });
        }
        if (groupBy === "week") {
          const weekStart = new Date(date);
          weekStart.setDate(date.getDate() - date.getDay());
          return weekStart.toLocaleDateString("en-US", { month: "short", day: "numeric" });
        }
        return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
      }

      function topCounts(items, selector, limit) {
        const counts = {};
        items.forEach((item) => {
          const value = selector(item);
          if (!value) return;
          counts[value] = (counts[value] || 0) + 1;
        });
        return Object.entries(counts)
          .sort(([, a], [, b]) => b - a)
          .slice(0, limit);
      }

      function normalizeCodeForCompare(code) {
        if (!code) return "";
        return String(code).trim().toLowerCase();
      }

      function isSuccessfulAnalyticsEntry(entry) {
        if (typeof entry.returned_count === "number") return entry.returned_count > 0;
        return Boolean(entry.occupation_title || entry.nco_code);
      }

      function parseAnalyticsDate(value) {
        const date = new Date(value);
        return Number.isNaN(date.getTime()) ? null : date;
      }

      function getAnalyticsTopN() {
        const input = document.getElementById("analyticsTopN");
        const value = parseInt(input?.value || "10", 10);
        const max = parseInt(input?.max || "20", 10);
        return Math.max(3, Math.min(value || 10, max));
      }

      function truncateLabel(value, length) {
        const text = String(value || "");
        return text.length > length ? `${text.slice(0, length)}...` : text;
      }

      function setTextContent(id, value) {
        const element = document.getElementById(id);
        if (element) element.textContent = value;
      }

      function setControlValue(id, value) {
        const element = document.getElementById(id);
        if (element) element.value = value;
      }

      function capitalize(value) {
        const text = String(value || "");
        return text ? text.charAt(0).toUpperCase() + text.slice(1) : "";
      }

      // Table functions
      function updateFilters() {
        refreshSearchFilterOptions();
        if (typeof refreshNcoFilterOptions === 'function') {
          refreshNcoFilterOptions();
        }
      }

      function getSearchFilterValues() {
        return {
          division: getMultiSelectValues("divisionFilter"),
          sub_division: getMultiSelectValues("subDivisionFilter"),
          group: getMultiSelectValues("groupFilter"),
          family: getMultiSelectValues("familyFilter"),
        };
      }

      function occupationMatchesSearchFilters(occupation, filters, skipField = "") {
        return Object.entries(filters).every(([field, values]) => {
          if (!values.length || field === skipField) return true;
          return values.includes(occupation[field] || "");
        });
      }

      function populateSearchFilter(selectId, allLabel, field, filters, changedId = "") {
        const root = document.getElementById(selectId);
        if (!root) return;
        const menu = root.querySelector(".multi-select-menu");
        if (!menu) return;

        const currentValues = getMultiSelectValues(selectId);
        menu.innerHTML = `
          <div class="multi-select-clear" onclick="resetMultiSelect('${selectId}')" style="padding: 10px 12px; cursor: pointer; border-bottom: 1px solid #e5e7eb; color: #475569; font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 8px; background: #f8fafc; transition: background 0.2s ease;" onmouseover="this.style.background='#f1f5f9'" onmouseout="this.style.background='#f8fafc'">
            <i class="fas fa-undo"></i> Reset Filter
          </div>
        `;

        const values = [...new Set(
          occupations
            .filter((occ) => occupationMatchesSearchFilters(occ, filters, field))
            .map((occ) => occ[field])
            .filter(Boolean)
        )].sort();

        values.forEach((value, index) => {
          const optionId = `${selectId}-${index}`;
          const label = document.createElement("label");
          label.className = "multi-select-option";
          label.innerHTML = `
            <input type="checkbox" id="${optionId}" value="${escapeHtml(value)}" ${currentValues.includes(value) ? "checked" : ""} onchange="handleMultiSelectChange('${selectId}')" />
            <span>${escapeHtml(value)}</span>
          `;
          menu.appendChild(label);
        });

        if (selectId !== changedId) {
          const validSelections = currentValues.filter((value) => values.includes(value));
          setMultiSelectValues(selectId, validSelections);
        }
        updateMultiSelectDisplay(selectId, allLabel);
      }

      function refreshSearchFilterOptions(changedId = "") {
        const filters = getSearchFilterValues();
        if (changedId !== "divisionFilter") populateSearchFilter("divisionFilter", "All Divisions", "division", filters, changedId);
        if (changedId !== "subDivisionFilter") populateSearchFilter("subDivisionFilter", "All Sub Divisions", "sub_division", filters, changedId);
        if (changedId !== "groupFilter") populateSearchFilter("groupFilter", "All Groups", "group", filters, changedId);
        if (changedId !== "familyFilter") populateSearchFilter("familyFilter", "All Families", "family", filters, changedId);
      }

      function updateSearchSubDivisionFilter() {
        refreshSearchFilterOptions("divisionFilter");
      }

      function updateSearchGroupFilter() {
        refreshSearchFilterOptions("subDivisionFilter");
      }

      function updateSearchFamilyFilter() {
        refreshSearchFilterOptions("groupFilter");
      }

      function toggleMultiSelect(selectId) {
        const root = document.getElementById(selectId);
        if (!root) return;
        document.querySelectorAll(".multi-select.open").forEach((select) => {
          if (select.id !== selectId) select.classList.remove("open");
        });
        root.classList.toggle("open");
      }

      function getMultiSelectValues(selectId) {
        const root = document.getElementById(selectId);
        if (!root) return [];
        return Array.from(root.querySelectorAll(".multi-select-menu input:checked"))
          .map((input) => input.value);
      }

      function setMultiSelectValues(selectId, values) {
        const selectedValues = new Set(values);
        const root = document.getElementById(selectId);
        if (!root) return;
        root.querySelectorAll(".multi-select-menu input").forEach((input) => {
          input.checked = selectedValues.has(input.value);
        });
      }

      function updateMultiSelectDisplay(selectId, allLabel) {
        const root = document.getElementById(selectId);
        const display = root?.querySelector(".multi-select-display");
        if (!display) return;
        const values = getMultiSelectValues(selectId);
        if (!values.length) {
          display.textContent = allLabel;
        } else if (values.length === 1) {
          display.textContent = values[0];
        } else {
          display.textContent = `${values.length} selected`;
        }
      }

      function handleMultiSelectChange(selectId) {
        if (selectId.startsWith("nco")) {
          const ncoLabelMap = {
            ncoDivisionFilter: "All Divisions",
            ncoSubDivisionFilter: "All Sub Divisions",
            ncoGroupFilter: "All Groups",
            ncoFamilyFilter: "All Families",
          };
          updateMultiSelectDisplay(selectId, ncoLabelMap[selectId] || "All");
          refreshNcoFilterOptions(selectId);
          drawNcoBubbleChart();
          return;
        }

        const labelMap = {
          divisionFilter: "All Divisions",
          subDivisionFilter: "All Sub Divisions",
          groupFilter: "All Groups",
          familyFilter: "All Families",
        };
        updateMultiSelectDisplay(selectId, labelMap[selectId] || "All");
        refreshSearchFilterOptions(selectId);
        filterOccupations();
      }

      function resetMultiSelect(selectId) {
        setMultiSelectValues(selectId, []);
        handleMultiSelectChange(selectId);
      }

      function resetAllDatabaseFilters() {
        ['divisionFilter', 'subDivisionFilter', 'groupFilter', 'familyFilter'].forEach(id => {
          setMultiSelectValues(id, []);
          const labelMap = {
            divisionFilter: "All Divisions",
            subDivisionFilter: "All Sub Divisions",
            groupFilter: "All Groups",
            familyFilter: "All Families",
          };
          updateMultiSelectDisplay(id, labelMap[id]);
        });
        const searchInput = document.getElementById('searchInput');
        if (searchInput) searchInput.value = '';
        const searchMode = document.getElementById('adminSearchMode');
        if (searchMode) searchMode.value = 'normal';
        
        refreshSearchFilterOptions();
        if (searchMode && searchMode.value === 'semantic') {
          searchOccupations();
        } else {
          filterOccupations();
        }
      }


      function escapeHtml(value) {
        return String(value || "")
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;")
          .replace(/'/g, "&#039;");
      }

      function displayTable() {
        const tbody = document.getElementById("occupationsTableBody");
        if (!tbody) return;

        const start = (currentPage - 1) * recordsPerPage;
        const end = start + recordsPerPage;
        const pageData = filteredOccupations.slice(start, end);

        let html = "";
        pageData.forEach((occupation) => {
          const ncoDisplay = occupation.nco_code
            ? `<span class="nco-code">${formatNcoCode(occupation.nco_code)}</span>`
            : `<span style="color:#9ca3af; font-style:italic;">No Code</span>`;
          html += `
            <tr>
              <td>${occupation.row_id}</td>
              <td>${escapeHtml(occupation.occupation_title)}</td>
              <td>${ncoDisplay}</td>
              <td>${escapeHtml(occupation.division || '—')}</td>
              <td>${escapeHtml(occupation.sub_division || '—')}</td>
              <td>${escapeHtml(occupation.group || '—')}</td>
              <td>${escapeHtml(occupation.family || '—')}</td>
              <td>
                <div class="action-buttons">
                  <button type="button" class="action-btn edit" onclick="editOccupation(${occupation.row_id})" title="Edit" aria-label="Edit occupation">
                    <i class="fas fa-edit" aria-hidden="true"></i>
                  </button>
                  <button type="button" class="action-btn history" onclick="showPromptHistory(${occupation.row_id})" title="View History" aria-label="View search history">
                    <i class="fas fa-clock" aria-hidden="true"></i>
                  </button>
                  <button type="button" class="action-btn delete" onclick="deleteOccupation(${occupation.row_id})" title="Delete" aria-label="Delete occupation">
                    <i class="fas fa-trash" aria-hidden="true"></i>
                  </button>
                </div>
              </td>
            </tr>
          `;
        });
        tbody.innerHTML = html;

        const recordCount = document.getElementById("recordCount");
        if (recordCount) {
          recordCount.textContent = `${filteredOccupations.length} records`;
        }

        updatePagination();
      }

      function updatePagination() {
        const totalPages = Math.ceil(filteredOccupations.length / recordsPerPage);
        const pagination = document.getElementById("pagination");
        if (!pagination) return;

        pagination.innerHTML = "";
        if (totalPages === 0) return;

        // Previous button
        const prevLi = document.createElement("li");
        prevLi.innerHTML = `<a class="page-link ${currentPage === 1 ? 'disabled' : ''}" href="#" onclick="changePage(${currentPage - 1})">Previous</a>`;
        pagination.appendChild(prevLi);

        // Page numbers
        const startPage = Math.max(1, currentPage - 2);
        const endPage = Math.min(totalPages, currentPage + 2);
        
        for (let i = startPage; i <= endPage; i++) {
          const li = document.createElement("li");
          li.innerHTML = `<a class="page-link ${i === currentPage ? 'active' : ''}" href="#" onclick="changePage(${i})">${i}</a>`;
          pagination.appendChild(li);
        }

        // Next button
        const nextLi = document.createElement("li");
        nextLi.innerHTML = `<a class="page-link ${currentPage === totalPages ? 'disabled' : ''}" href="#" onclick="changePage(${currentPage + 1})">Next</a>`;
        pagination.appendChild(nextLi);
      }

      function changePage(page) {
        const totalPages = Math.ceil(filteredOccupations.length / recordsPerPage);
        if (page < 1 || page > totalPages) return;
        
        currentPage = page;
        displayTable();
      }

      // Search and filter functions
      function searchOccupations() {
        currentSearchTerm = document.getElementById("searchInput").value.trim();
        currentPage = 1;
        clearTimeout(semanticSearchTimer);
        const mode = getAdminSearchMode();
        semanticSearchTimer = setTimeout(() => applyFilters(), mode === "semantic" ? 300 : 200);
      }

      function applyFilters() {
        if (getAdminSearchMode() === "semantic" && currentSearchTerm) {
          runSemanticOccupationSearch(currentSearchTerm);
          return;
        }

        semanticSearchResults = [];
        setAdminSearchStatus("");
        applyOccupationFilters(occupations, true);
      }

      function applyOccupationFilters(sourceOccupations, includeTextSearch) {
        const filters = getSearchFilterValues();
        const searchTerm = (currentSearchTerm || "").toLowerCase();

        filteredOccupations = sourceOccupations.filter((occupation) => {
          const divisionMatch = !filters.division.length || filters.division.includes(occupation.division || "");
          const subDivisionMatch = !filters.sub_division.length || filters.sub_division.includes(occupation.sub_division || "");
          const groupMatch = !filters.group.length || filters.group.includes(occupation.group || "");
          const familyMatch = !filters.family.length || filters.family.includes(occupation.family || "");

          if (!includeTextSearch || !searchTerm) {
            return divisionMatch && subDivisionMatch && groupMatch && familyMatch;
          }

          const searchFields = [
            occupation.occupation_title,
            occupation.description,
            occupation.division,
            occupation.sub_division,
            occupation.group,
            occupation.family,
            occupation.nco_code,
            occupation.nco_2004_code
          ].filter(Boolean);
          
          const textMatch = searchFields.some(field => 
            field.toLowerCase().includes(searchTerm)
          );
          
          return textMatch && divisionMatch && subDivisionMatch && groupMatch && familyMatch;
        });

        currentPage = 1;
        displayTable();
      }

      function filterOccupations() {
        const evt = typeof event !== "undefined" ? event : null;
        const changedId = evt && evt.target ? evt.target.id : "";
        if (!evt || !evt.target || !evt.target.closest || !evt.target.closest(".multi-select-menu")) {
          refreshSearchFilterOptions(changedId);
        }

        currentPage = 1;
        if (getAdminSearchMode() === "semantic" && currentSearchTerm && semanticSearchResults.length) {
          applyOccupationFilters(semanticSearchResults, false);
          setAdminSearchStatus(`Showing ${filteredOccupations.length} filtered semantic matches`);
          return;
        }
        applyFilters();
      }

      function getAdminSearchMode() {
        const modeSelect = document.getElementById("adminSearchMode");
        return modeSelect ? modeSelect.value : "normal";
      }

      function setAdminSearchStatus(message) {
        const status = document.getElementById("adminSearchStatus");
        if (status) status.textContent = message || "";
      }

      function runSemanticOccupationSearch(query) {
        const requestId = ++semanticSearchRequestId;
        setAdminSearchStatus("Searching with Semantic search...");

        fetch("/api/search", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query,
            search_mode: "general",
            top_k: 100
          })
        })
          .then((response) => response.json())
          .then((data) => {
            if (requestId !== semanticSearchRequestId) return;
            if (data.error) {
              throw new Error(data.error);
            }

            const rankedResults = Array.isArray(data.results) ? data.results : [];
            const rankedOccupations = rankedResults
              .map((result) => {
                if (Number.isInteger(result.row_id)) {
                  return occupations.find((occupation) => occupation.row_id === result.row_id);
                }
                const resultCode = normalizeCodeForCompare(result.nco_code || result.nco_2015 || "");
                return occupations.find((occupation) => normalizeCodeForCompare(occupation.nco_code) === resultCode);
              })
              .filter(Boolean);

            semanticSearchResults = rankedOccupations;
            applyOccupationFilters(semanticSearchResults, false);
            setAdminSearchStatus(`Showing ${filteredOccupations.length} of ${rankedOccupations.length} semantic matches`);
          })
          .catch((error) => {
            if (requestId !== semanticSearchRequestId) return;
            console.error("Semantic admin search failed:", error);
            semanticSearchResults = [];
            filteredOccupations = [];
            displayTable();
            setAdminSearchStatus("Semantic search failed. Try normal table search.");
          });
      }

      function normalizeCodeForCompare(value) {
        return String(value || "").replace(/\s+/g, "").toLowerCase();
      }

      function refreshData() {
        loadOccupations();
        showNotification("Data refreshed successfully", "success");
      }

      // CRUD operations
      function editOccupation(rowId) {
        const occupation = occupations.find((occ) => occ.row_id === rowId);
        if (!occupation) return;

        // Populate basic fields
        document.getElementById("editRowId").value = occupation.row_id;
        document.getElementById("editTitle").value = occupation.occupation_title || "";
        document.getElementById("editAdminPassword").value = "";
        document.getElementById("editDescription").value = occupation.description || "";

        // Handle NCO code split
        const ncoCode = formatNcoCode(occupation.nco_code || "");
        const parts = ncoCode.split(".");
        if (parts.length === 2) {
          document.getElementById("editNcoCodeFirst").value = parts[0];
          document.getElementById("editNcoCodeSecond").value = parts[1];
        }

        const hasNco2004 = !!(occupation.nco_2004_code || "").trim();
        const editNco2004Row = document.getElementById("editNco2004Row");
        const editNco2004First = document.getElementById("editNco2004CodeFirst");
        const editNco2004Second = document.getElementById("editNco2004CodeSecond");
        if (hasNco2004) {
          const parts2004 = (occupation.nco_2004_code || "").split(".");
          editNco2004First.value = parts2004[0] || "";
          editNco2004Second.value = parts2004[1] || "";
          editNco2004First.disabled = false;
          editNco2004Second.disabled = false;
          editNco2004Row.style.display = "";
        } else {
          editNco2004First.value = "";
          editNco2004Second.value = "";
          editNco2004First.disabled = true;
          editNco2004Second.disabled = true;
          editNco2004Row.style.display = "none";
        }

        // Populate division/sub division/group/family dropdowns
        populateDivisionDropdowns();
        document.getElementById("editDivision").value = occupation.division || "";
        updateSubDivisionDropdown("editDivision", "editSubDivision");
        document.getElementById("editSubDivision").value = occupation.sub_division || "";
        updateGroupDropdown("editDivision", "editSubDivision", "editGroup");
        document.getElementById("editGroup").value = occupation.group || "";
        updateFamilyDropdown("editDivision", "editSubDivision", "editGroup", "editFamily");
        document.getElementById("editFamily").value = occupation.family || "";

        // Show modal using Bootstrap 5
        showModalById("editModal");
      }

      function buildNcoCode(firstId, secondId, expectedSecondLength) {
        const first = (document.getElementById(firstId).value || "").trim();
        const second = (document.getElementById(secondId).value || "").trim();
        if (!/^\d{4}$/.test(first)) {
          return { ok: false, error: "First segment must be exactly 4 digits" };
        }
        const secondRegex = new RegExp(`^\\d{${expectedSecondLength}}$`);
        if (!secondRegex.test(second)) {
          return { ok: false, error: `Second segment must be exactly ${expectedSecondLength} digits` };
        }
        return { ok: true, code: `${first}.${second}` };
      }

      function validateOccupationPayload(payload, requireNco2004) {
        if (!payload.occupation_title) return "Occupation title is required";
        if (!payload.division) return "Division is required";
        if (!payload.sub_division) return "Sub Division is required";
        if (!payload.group) return "Group is required";
        if (!payload.family) return "Family is required";
        if (!payload.description) return "Occupation description is required";
        if (!payload.admin_password) return "Admin password is required";
        if (!/^\d{4}\.\d{4}$/.test(payload.nco_code || "")) return "NCO 2015 must be in XXXX.XXXX format";
        if (requireNco2004 && !/^\d{4}\.\d{2}$/.test(payload.nco_2004_code || "")) return "NCO 2004 must be in XXXX.XX format";
        if (payload.nco_2004_code && !/^\d{4}\.\d{2}$/.test(payload.nco_2004_code)) return "NCO 2004 must be in XXXX.XX format";
        return "";
      }

      function saveOccupation() {
        const rowId = document.getElementById("editRowId").value;
        const nco2015 = buildNcoCode("editNcoCodeFirst", "editNcoCodeSecond", 4);
        if (!nco2015.ok) {
          showNotification(nco2015.error, "error");
          return;
        }
        const nco2004RowVisible = document.getElementById("editNco2004Row").style.display !== "none";
        let nco2004Code = "";
        if (nco2004RowVisible) {
          const nco2004 = buildNcoCode("editNco2004CodeFirst", "editNco2004CodeSecond", 2);
          if (!nco2004.ok) {
            showNotification(nco2004.error, "error");
            return;
          }
          nco2004Code = nco2004.code;
        }

        const data = {
          row_id: parseInt(rowId),
          occupation_title: (document.getElementById("editTitle").value || "").trim(),
          nco_code: nco2015.code,
          nco_2004_code: nco2004Code,
          description: (document.getElementById("editDescription").value || "").trim(),
          division: (document.getElementById("editDivision").value || "").trim(),
          sub_division: (document.getElementById("editSubDivision").value || "").trim(),
          group: (document.getElementById("editGroup").value || "").trim(),
          family: (document.getElementById("editFamily").value || "").trim(),
          admin_password: (document.getElementById("editAdminPassword").value || "").trim(),
        };
        const validationError = validateOccupationPayload(data, nco2004RowVisible);
        if (validationError) {
          showNotification(validationError, "error");
          return;
        }

        showLoading();
        fetch(`/admin/api/occupations/${rowId}`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(data),
        })
          .then((response) => response.json())
          .then((result) => {
            if (result.success) {
              const editModal = bootstrap.Modal.getInstance(document.getElementById("editModal"));
              if (editModal) {
                editModal.hide();
              }
              loadOccupations();
              showNotification("Occupation updated successfully", "success");
            } else {
              showNotification(result.error || "Failed to update occupation", "error");
            }
          })
          .catch((error) => {
            console.error("Error updating occupation:", error);
            showNotification("Failed to update occupation", "error");
          })
          .finally(() => {
            hideLoading();
          });
      }

      function showAddModal() {
        document.getElementById("addForm").reset();
        document.getElementById("addAdminPassword").value = "";
        populateDivisionDropdowns();
        document.getElementById("addSubDivision").innerHTML = '<option value="">Select Sub Division</option>';
        document.getElementById("addGroup").innerHTML = '<option value="">Select Group</option>';
        document.getElementById("addFamily").innerHTML = '<option value="">Select Family</option>';
        showModalById("addModal");
      }

      function cleanupStuckModalState() {
        document.body.classList.remove('modal-open');
        document.querySelectorAll('.modal-backdrop').forEach((el) => el.remove());
        document.body.style.removeProperty('padding-right');
      }

      function showModalById(modalId) {
        cleanupStuckModalState();

        const modalEl = document.getElementById(modalId);
        if (!modalEl) return;

        // Ensure modal is a direct child of body to avoid z-index / stacking issues
        if (modalEl.parentElement !== document.body) {
          document.body.appendChild(modalEl);
        }

        // Ensure interactive layering
        modalEl.style.zIndex = '1055';

        const modal = bootstrap.Modal.getOrCreateInstance(modalEl, {
          backdrop: true,
          keyboard: true,
          focus: true,
        });

        modalEl.addEventListener('hidden.bs.modal', cleanupStuckModalState, { once: true });
        modal.show();
      }

      // Helper functions for dropdowns
      function populateDivisionDropdowns() {
        const divisions = [...new Set(occupations.map((occ) => occ.division).filter((d) => d))];
        
        // Update edit modal division dropdown
        const editDivisionSelect = document.getElementById("editDivision");
        if (editDivisionSelect) {
          editDivisionSelect.innerHTML = '<option value="">Select Division</option>';
          divisions.forEach((division) => {
            editDivisionSelect.innerHTML += `<option value="${division}">${division}</option>`;
          });
        }
        
        // Update add modal division dropdown
        const addDivisionSelect = document.getElementById("addDivision");
        if (addDivisionSelect) {
          addDivisionSelect.innerHTML = '<option value="">Select Division</option>';
          divisions.forEach((division) => {
            addDivisionSelect.innerHTML += `<option value="${division}">${division}</option>`;
          });
        }
      }

      function updateSubDivisionDropdown(divisionSelectId, subDivisionSelectId) {
        const divisionSelect = document.getElementById(divisionSelectId);
        const subDivisionSelect = document.getElementById(subDivisionSelectId);
        if (!divisionSelect || !subDivisionSelect) return;
        const selectedDivision = divisionSelect.value;
        subDivisionSelect.innerHTML = '<option value="">Select Sub Division</option>';
        if (!selectedDivision) return;
        const subDivisions = [...new Set(
          occupations
            .filter((occ) => (occ.division || "") === selectedDivision)
            .map((occ) => occ.sub_division)
            .filter((s) => s)
        )];
        subDivisions.forEach((subDivision) => {
          subDivisionSelect.innerHTML += `<option value="${subDivision}">${subDivision}</option>`;
        });
      }

      function updateGroupDropdown(divisionSelectId, subDivisionSelectId, groupSelectId) {
        const divisionSelect = document.getElementById(divisionSelectId);
        const subDivisionSelect = document.getElementById(subDivisionSelectId);
        const groupSelect = document.getElementById(groupSelectId);
        if (!divisionSelect || !subDivisionSelect || !groupSelect) return;
        const selectedDivision = divisionSelect.value;
        const selectedSubDivision = subDivisionSelect.value;
        groupSelect.innerHTML = '<option value="">Select Group</option>';
        if (!selectedDivision || !selectedSubDivision) return;
        const groups = [...new Set(
          occupations
            .filter((occ) => (occ.division || "") === selectedDivision && (occ.sub_division || "") === selectedSubDivision)
            .map((occ) => occ.group)
            .filter((g) => g)
        )];
        groups.forEach((groupValue) => {
          groupSelect.innerHTML += `<option value="${groupValue}">${groupValue}</option>`;
        });
      }

      function updateFamilyDropdown(divisionSelectId, subDivisionSelectId, groupSelectId, familySelectId) {
        const divisionSelect = document.getElementById(divisionSelectId);
        const subDivisionSelect = document.getElementById(subDivisionSelectId);
        const groupSelect = document.getElementById(groupSelectId);
        const familySelect = document.getElementById(familySelectId);
        if (!divisionSelect || !subDivisionSelect || !groupSelect || !familySelect) return;
        const selectedDivision = divisionSelect.value;
        const selectedSubDivision = subDivisionSelect.value;
        const selectedGroup = groupSelect.value;
        familySelect.innerHTML = '<option value="">Select Family</option>';
        if (!selectedDivision || !selectedSubDivision || !selectedGroup) return;
        const families = [...new Set(
          occupations
            .filter((occ) =>
              (occ.division || "") === selectedDivision &&
              (occ.sub_division || "") === selectedSubDivision &&
              (occ.group || "") === selectedGroup
            )
            .map((occ) => occ.family)
            .filter((f) => f)
        )];
        families.forEach((family) => {
          familySelect.innerHTML += `<option value="${family}">${family}</option>`;
        });
      }

      // Add event listeners for division changes
      document.addEventListener("DOMContentLoaded", function() {
        // Edit modal division change
        const editDivisionSelect = document.getElementById("editDivision");
        if (editDivisionSelect) {
          editDivisionSelect.addEventListener("change", function() {
            updateSubDivisionDropdown("editDivision", "editSubDivision");
            document.getElementById("editGroup").innerHTML = '<option value="">Select Group</option>';
            document.getElementById("editFamily").innerHTML = '<option value="">Select Family</option>';
          });
        }
        const editSubDivisionSelect = document.getElementById("editSubDivision");
        if (editSubDivisionSelect) {
          editSubDivisionSelect.addEventListener("change", function() {
            updateGroupDropdown("editDivision", "editSubDivision", "editGroup");
            document.getElementById("editFamily").innerHTML = '<option value="">Select Family</option>';
          });
        }
        const editGroupSelect = document.getElementById("editGroup");
        if (editGroupSelect) {
          editGroupSelect.addEventListener("change", function() {
            updateFamilyDropdown("editDivision", "editSubDivision", "editGroup", "editFamily");
          });
        }

        const addDivisionSelect = document.getElementById("addDivision");
        if (addDivisionSelect) {
          addDivisionSelect.addEventListener("change", function() {
            updateSubDivisionDropdown("addDivision", "addSubDivision");
            document.getElementById("addGroup").innerHTML = '<option value="">Select Group</option>';
            document.getElementById("addFamily").innerHTML = '<option value="">Select Family</option>';
          });
        }
        const addSubDivisionSelect = document.getElementById("addSubDivision");
        if (addSubDivisionSelect) {
          addSubDivisionSelect.addEventListener("change", function() {
            updateGroupDropdown("addDivision", "addSubDivision", "addGroup");
            document.getElementById("addFamily").innerHTML = '<option value="">Select Family</option>';
          });
        }
        const addGroupSelect = document.getElementById("addGroup");
        if (addGroupSelect) {
          addGroupSelect.addEventListener("change", function() {
            updateFamilyDropdown("addDivision", "addSubDivision", "addGroup", "addFamily");
          });
        }

        document.addEventListener("click", function(evt) {
          if (evt.target.closest && evt.target.closest(".multi-select")) return;
          document.querySelectorAll(".multi-select.open").forEach((select) => {
            select.classList.remove("open");
          });
        });

        const ncoInputs = [
          { a: document.getElementById('addNcoCodeFirst'), b: document.getElementById('addNcoCodeSecond') },
          { a: document.getElementById('addNco2004CodeFirst'), b: document.getElementById('addNco2004CodeSecond') },
          { a: document.getElementById('editNcoCodeFirst'), b: document.getElementById('editNcoCodeSecond') },
          { a: document.getElementById('editNco2004CodeFirst'), b: document.getElementById('editNco2004CodeSecond') },
        ];

        ncoInputs.forEach(({ a, b }) => {
          if (a) {
            a.addEventListener('input', () => {
              a.value = (a.value || '').replace(/\D/g, '').slice(0, 4);
              if (a.value.length === 4 && b) b.focus();
            });
          }
          if (b) {
            const max = b.id.toLowerCase().includes("2004") ? 2 : 4;
            b.addEventListener('input', () => {
              b.value = (b.value || '').replace(/\D/g, '').slice(0, max);
            });
          }
        });
      });

      function addOccupation() {
        const nco2015 = buildNcoCode("addNcoCodeFirst", "addNcoCodeSecond", 4);
        if (!nco2015.ok) {
          showNotification(nco2015.error, "error");
          return;
        }

        const data = {
          occupation_title: (document.getElementById("addTitle").value || "").trim(),
          nco_code: nco2015.code,
          nco_2004_code: "",
          description: (document.getElementById("addDescription").value || "").trim(),
          division: (document.getElementById("addDivision").value || "").trim(),
          sub_division: (document.getElementById("addSubDivision").value || "").trim(),
          group: (document.getElementById("addGroup").value || "").trim(),
          family: (document.getElementById("addFamily").value || "").trim(),
          admin_password: (document.getElementById("addAdminPassword").value || "").trim(),
        };
        const validationError = validateOccupationPayload(data, false);
        if (validationError) {
          showNotification(validationError, "error");
          return;
        }

        showLoading();
        fetch("/admin/api/occupations", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(data),
        })
          .then((response) => response.json())
          .then((result) => {
            if (result.success) {
              const addModal = bootstrap.Modal.getInstance(document.getElementById("addModal"));
              if (addModal) {
                addModal.hide();
              }
              loadOccupations();
              showNotification("Occupation added successfully", "success");
            } else {
              showNotification(result.error || "Failed to add occupation", "error");
            }
          })
          .catch((error) => {
            console.error("Error adding occupation:", error);
            showNotification("Failed to add occupation", "error");
          })
          .finally(() => {
            hideLoading();
          });
      }

      async function loadAnalyticsData() {
        if (window.analyticsLoading) {
          return;
        }
        window.analyticsLoading = true;
        
        const overlay = document.getElementById('globalLoadingOverlay');
        if (overlay && !window._initialLoadComplete) {
            overlay.classList.remove('hidden');
        }

        try {
          const response = await fetch(`/admin/api/prompt-history?limit=${ANALYTICS_HISTORY_LIMIT}`);
          if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
          }
          const historyData = await response.json();
          if (!Array.isArray(historyData)) {
            throw new Error("Invalid history data");
          }
          updateSearchAnalyticsCharts(historyData);
          updateLastUpdateTime();
        } catch (error) {
          console.error("Error loading analytics data:", error);
          showNotification("Failed to load analytics data", "error");
        } finally {
          window.analyticsLoading = false;
          if (overlay && !window._initialLoadComplete) {
              overlay.classList.add('hidden');
              window._initialLoadComplete = true;
          }
        }
      }

      // Refresh button click handler
      async function refreshAnalytics() {
        const btn = document.getElementById('refreshAnalyticsBtn') || document.querySelector('.refresh-btn');
        const originalContent = btn ? btn.innerHTML : '';
        if (btn) {
          btn.innerHTML = '<i class="fas fa-sync-alt fa-spin"></i> Refreshing...';
          btn.disabled = true;
        }
        
        try {
          await loadAnalyticsData();
          showNotification('Analytics refreshed successfully', 'success');
        } catch (error) {
          showNotification('Failed to refresh analytics', 'error');
        } finally {
          if (btn) {
            btn.innerHTML = originalContent;
            btn.disabled = false;
          }
        }
      }

      // Tab switching functionality
      function switchTab(tabName, element) {
        // Hide all tabs
        document.querySelectorAll('.tab-content').forEach(tab => {
          tab.classList.remove('active');
        });
        
        // Remove active class from all tab buttons
        document.querySelectorAll('.tab-button').forEach(btn => {
          btn.classList.remove('active');
        });
        
        // Show selected tab
        const targetTab = document.getElementById(tabName);
        if (targetTab) {
          targetTab.classList.add('active');
        }
        
        if (element) {
          element.classList.add('active');
        }
        
        // Load data based on which tab is now active
        if (tabName === 'analytics-tab') {
          loadAnalyticsData();
          startAnalyticsAutoRefresh();
        } else if (tabName === 'database-tab') {
          if (occupations.length === 0) {
            loadOccupations();
          } else {
            displayTable();
          }
          if (refreshInterval) {
            clearInterval(refreshInterval);
            refreshInterval = null;
          }
        } else if (tabName === 'nco-analysis-tab') {
          if (refreshInterval) {
            clearInterval(refreshInterval);
            refreshInterval = null;
          }
          // Load India map when tab is activated
          setTimeout(() => initIndiaMap(), 100);
        }
      }

      function deleteOccupation(rowId) {
        if (!confirm("Are you sure you want to delete this occupation? This action cannot be undone.")) {
          return;
        }

        showLoading();
        fetch(`/admin/api/occupations/${rowId}`, {
          method: "DELETE",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ admin_password: prompt("Enter admin password to confirm deletion:") || "" }),
        })
          .then((response) => response.json())
          .then((result) => {
            if (result.success) {
              loadOccupations();
              showNotification("Occupation deleted successfully", "success");
            } else {
              showNotification(result.error || "Failed to delete occupation", "error");
            }
          })
          .catch((error) => {
            console.error("Error deleting occupation:", error);
            showNotification("Failed to delete occupation", "error");
          })
          .finally(() => {
            hideLoading();
          });
      }

      // History functions
      function showPromptHistory(rowId) {
        const occupation = occupations.find((occ) => occ.row_id === rowId);
        if (!occupation) return;

        currentHistoryOccupationTitle = occupation.occupation_title;
        document.getElementById("historyOccupation").textContent = currentHistoryOccupationTitle;
        
        refreshPromptHistory();
        showModalById("historyModal");
      }

      function refreshPromptHistory() {
        if (!currentHistoryOccupationTitle) return;

        showLoading();
        fetch(`/admin/api/prompt-history?occupation_title=${encodeURIComponent(currentHistoryOccupationTitle)}&limit=100`)
          .then((response) => response.json())
          .then((data) => {
            currentHistoryRows = Array.isArray(data) ? data : [];
            displayPromptHistory();
          })
          .catch((error) => {
            console.error("Error loading prompt history:", error);
            currentHistoryRows = [];
            displayPromptHistory();
          })
          .finally(() => {
            hideLoading();
          });
      }

      function displayPromptHistory() {
        const tbody = document.getElementById("historyTableBody");
        const emptyDiv = document.getElementById("historyEmpty");

        if (currentHistoryRows.length === 0) {
          tbody.innerHTML = "";
          emptyDiv.style.display = "block";
          return;
        }

        emptyDiv.style.display = "none";
        tbody.innerHTML = currentHistoryRows.map((row) => {
          let location = 'Unknown';
          if (row.geo_city && row.geo_state) {
            location = `${row.geo_city}, ${row.geo_state}`;
          } else if (row.geo_state && row.geo_country) {
            location = `${row.geo_state}, ${row.geo_country}`;
          } else if (row.geo_country) {
            location = row.geo_country;
          }
          return `<tr>
            <td>${new Date(row.ts).toLocaleString()}</td>
            <td>${row.query}</td>
            <td>${row.top_k || '-'}</td>
            <td>${row.returned_count || '-'}</td>
            <td>${location}</td>
          </tr>`;
        }).join('');
      }

      function filterPromptHistory() {
        const searchTerm = document.getElementById("historySearch").value.toLowerCase();
        const filtered = currentHistoryRows.filter((row) => 
          row.query.toLowerCase().includes(searchTerm)
        );
        
        const tbody = document.getElementById("historyTableBody");
        const emptyDiv = document.getElementById("historyEmpty");

        if (filtered.length === 0) {
          tbody.innerHTML = "";
          emptyDiv.style.display = "block";
          return;
        }

        emptyDiv.style.display = "none";
        tbody.innerHTML = filtered.map((row) => {
          let location = 'Unknown';
          if (row.geo_city && row.geo_state) {
            location = `${row.geo_city}, ${row.geo_state}`;
          } else if (row.geo_state && row.geo_country) {
            location = `${row.geo_state}, ${row.geo_country}`;
          } else if (row.geo_country) {
            location = row.geo_country;
          }
          return `<tr>
            <td>${new Date(row.ts).toLocaleString()}</td>
            <td>${row.query}</td>
            <td>${row.top_k || '-'}</td>
            <td>${row.returned_count || '-'}</td>
            <td>${location}</td>
          </tr>`;
        }).join('');
      }

      // Utility functions
      function formatNcoCode(code) {
        if (!code) return "";
        const parts = code.split(".");
        if (parts.length === 2) {
          const left = parts[0].padStart(4, "0");
          const right = parts[1].padStart(4, "0");
          return `${left}.${right}`;
        }
        return code;
      }

      function showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        notification.innerHTML = `
          ${message}
          <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.body.appendChild(notification);

        setTimeout(() => {
          notification.remove();
        }, 5000);
      }

      function updateLastUpdateTime() {
        const now = new Date();
        const timeString = now.toLocaleString(undefined, {
          year: 'numeric',
          month: 'short',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit'
        });

        const lastUpdateTimeElement = document.getElementById('lastUpdateTime');
        if (lastUpdateTimeElement) {
          lastUpdateTimeElement.textContent = `Last updated: ${timeString}`;
        }

        const lastUpdatedElement = document.getElementById('lastUpdated');
        if (lastUpdatedElement) {
          lastUpdatedElement.textContent = timeString;
        }
        
        const reportTotalRecordsElement = document.getElementById('reportTotalRecords');
        if (reportTotalRecordsElement) {
          reportTotalRecordsElement.textContent = occupations.length.toLocaleString();
        }
      }

      // Chart refresh functions
      function refreshChart(chartName) {
        if (chartName === 'divisionChart') {
          updateChartsData();
        } else if (chartName === 'trendsChart') {
          loadAnalyticsData();
        }
        showNotification('Chart refreshed', 'success');
      }

      function refreshAnalyticsCharts() {
        updateChartsData();
        loadAnalyticsData();
      }

      function loadSearchAnalytics() {
        loadAnalyticsData();
      }

      function toggleAnalyticsSidebar() {
        const sidebar = document.getElementById('analyticsSidebar');
        if (sidebar.classList.contains('collapsed')) {
          sidebar.classList.remove('collapsed');
        } else {
          sidebar.classList.add('collapsed');
        }
      }

      // UI update functions for interactive filters
      function updateDateRangeUI(radio) {
        document.querySelectorAll('#dateRangeChips .chip').forEach(c => c.classList.remove('active'));
        radio.parentElement.classList.add('active');
        document.getElementById('analyticsDateRange').value = radio.value;
        
        const customDates = document.getElementById('customDatesContainer');
        if (radio.value === 'custom') {
          customDates.style.display = 'block';
        } else {
          customDates.style.display = 'none';
        }
        
        applyAnalyticsControls();
      }

      function updateGroupByUI(radio) {
        document.getElementById('analyticsGroupBy').value = radio.value;
        applyAnalyticsControls();
      }

      function updateOutcomeUI(radio) {
        document.querySelectorAll('#outcomeChips .chip').forEach(c => c.classList.remove('active'));
        radio.parentElement.classList.add('active');
        document.getElementById('analyticsOutcomeFilter').value = radio.value;
        applyAnalyticsControls();
      }

      async function ensureXlsxLoaded() {
        if (window.XLSX) return;
        await new Promise((resolve, reject) => {
          const script = document.createElement("script");
          script.src = "https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js";
          script.async = true;
          script.onload = resolve;
          script.onerror = () => reject(new Error("Failed to load Excel export library"));
          document.body.appendChild(script);
        });
      }

      async function exportData(format) {
        if (!filteredOccupations || filteredOccupations.length === 0) {
          showNotification("No data to export", "error");
          return;
        }

        const data = filteredOccupations.map(occ => ({
          "Row ID": occ.row_id || "",
          "Occupation Title": occ.occupation_title || "",
          "NCO Code": occ.nco_code || "",
          "NCO 2004 Code": occ.nco_2004_code || "",
          "Division": occ.division || "",
          "Sub Division": occ.sub_division || "",
          "Group": occ.group || "",
          "Family": occ.family || "",
          "Description": occ.description || ""
        }));

        const date = new Date().toISOString().split('T')[0];

        if (format === 'excel') {
          try {
            await ensureXlsxLoaded();
          } catch (error) {
            showNotification("Excel export library is not available.", "error");
            return;
          }
          const worksheet = XLSX.utils.json_to_sheet(data);
          const workbook = XLSX.utils.book_new();
          XLSX.utils.book_append_sheet(workbook, worksheet, "Occupations");
          XLSX.writeFile(workbook, `occupations_export_${date}.xlsx`);
          showNotification("Excel export downloaded successfully", "success");
        } else {
          // CSV Export
          const headers = Object.keys(data[0]);
          const csvRows = [headers.join(",")];
          
          function escapeCSV(str) {
            if (str == null) return '""';
            const stringified = String(str);
            if (stringified.search(/("|,|\n)/g) >= 0) {
              return `"${stringified.replace(/"/g, '""')}"`;
            }
            return stringified;
          }

          data.forEach(rowObj => {
            const row = headers.map(header => escapeCSV(rowObj[header]));
            csvRows.push(row.join(","));
          });
          
          const csvString = csvRows.join("\\n");
          const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
          
          const link = document.createElement("a");
          const url = URL.createObjectURL(blob);
          link.setAttribute("href", url);
          link.setAttribute("download", `occupations_export_${date}.csv`);
          link.style.visibility = 'hidden';
          
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          showNotification("CSV export downloaded successfully", "success");
        }
          // Legacy NCO Search Demand Explorer and Bubble Chart code removed
      }

      // ========================================================
      // INDIA MAP — State-wise Occupation Demand Analysis
      // Performance-optimised: rAF-throttled hover, direct element
      // tracking for selection highlight, in-place Chart.js updates.
      // ========================================================

      let stateDivisionChartInstance = null;
      let _mapSelectedEl = null;   // direct ref to the selected <path> DOM node
      let _mapStateMap   = {};     // stateName -> count (kept for re-colour on refresh)
      let _mapSvgSelection = null; // d3 selection of the SVG — reused across calls

      // ----------------------------------------------------------
      // Helper: get the state name from a GeoJSON feature
      // ----------------------------------------------------------
      function _getStateName(feature) {
        return (
          feature.properties?.NAME_1 ||
          feature.properties?.st_nm  ||
          feature.properties?.name   ||
          ''
        );
      }

      // ----------------------------------------------------------
      // _renderIntlBox — populate the international searches panel
      // ----------------------------------------------------------
      function _renderIntlBox(data) {
        const list  = document.getElementById('intlCountryList');
        const badge = document.getElementById('intlBadge');
        if (!list || !badge) return;

        const total = data.reduce((s, d) => s + d.count, 0);
        badge.textContent = total > 0
          ? total.toLocaleString() + ' search' + (total !== 1 ? 'es' : '')
          : 'No data';

        list.innerHTML = '';
        if (!data.length) {
          list.innerHTML = '<span style="font-size:12px;color:#94a3b8;">No searches from outside India yet.</span>';
          return;
        }

        const max = data[0].count;
        data.forEach(d => {
          const pct = max ? Math.round(d.count / max * 100) : 0;
          const tile = document.createElement('div');
          tile.style.cssText =
            'display:flex;flex-direction:column;gap:4px;background:#f8fafc;border:1px solid #e2e8f0;'
            + 'border-radius:10px;padding:10px 14px;min-width:150px;flex:1;';
          tile.innerHTML =
            '<div style="display:flex;align-items:center;justify-content:space-between;gap:6px;">'
            + '<span style="font-size:13px;font-weight:600;color:#1e293b;">' + d.country + '</span>'
            + '<span style="font-size:12px;font-weight:700;color:#6366f1;">' + d.count.toLocaleString() + '</span>'
            + '</div>'
            + '<div style="height:4px;background:#e2e8f0;border-radius:4px;">'
            + '<div style="height:4px;width:' + pct + '%;background:#6366f1;border-radius:4px;"></div>'
            + '</div>';
          list.appendChild(tile);
        });
      }

      // ----------------------------------------------------------
      // initIndiaMap
      // ----------------------------------------------------------
      async function initIndiaMap() {
        const container = document.getElementById('indiaMapContainer');
        if (!container) return;

        // Show loading only when GeoJSON isn't cached yet
        if (!window.__ncoIndiaGeoData) {
          container.innerHTML =
            '<div style="color:#94a3b8;font-size:14px;"><i class="fas fa-spinner fa-spin"></i>\u00a0Loading map…</div>';
        }

        // ── 1. Fetch state counts, GeoJSON, and international counts in parallel ──
        let stateData = [];
        let geoData;

        try {
          const [statsRes, geoRes, intlRes] = await Promise.all([
            fetch('/admin/api/analytics/states'),
            window.__ncoIndiaGeoData
              ? Promise.resolve(null)   // skip network if already cached
              : fetch('https://raw.githubusercontent.com/geohacker/india/master/state/india_state.geojson'),
            fetch('/admin/api/analytics/countries')
          ]);

          stateData = await statsRes.json();
          if (!Array.isArray(stateData)) stateData = [];

          if (geoRes) {
            geoData = await geoRes.json();
            window.__ncoIndiaGeoData = geoData;
          } else {
            geoData = window.__ncoIndiaGeoData;
          }

          const intlData = await intlRes.json();
          _renderIntlBox(Array.isArray(intlData) ? intlData : []);

        } catch (e) {
          console.error('India map fetch error:', e);
          container.innerHTML =
            '<div style="color:#ef4444;font-size:13px;padding:20px;text-align:center;">'
            + '<i class="fas fa-exclamation-triangle"></i>\u00a0Could not load India map. Check internet connection.</div>';
          return;
        }

        // ── 2. Build lookup and update metric strip ────────────
        _mapStateMap = {};
        let totalAll = 0;
        stateData.forEach(d => { _mapStateMap[d.state] = d.count; totalAll += d.count; });

        const counts      = Object.values(_mapStateMap);
        const activeStates = counts.length;
        const topState    = stateData.length ? stateData[0].state : '\u2014';
        document.getElementById('mapMetricTotal').textContent    = totalAll.toLocaleString();
        document.getElementById('mapMetricStates').textContent   = activeStates;
        document.getElementById('mapMetricTopState').textContent = topState || '\u2014';
        document.getElementById('mapMetricTopOcc').textContent   = '\u2014';

        const minCount = counts.length ? Math.min(...counts) : 0;
        const maxCount = counts.length ? Math.max(...counts) : 1;
        const allSame  = minCount === maxCount;

        const colorScale = d3.scaleLinear()
          .domain(allSame ? [0, 1] : [minCount, maxCount])
          .range(['#dbeafe', '#1e3a8a'])
          .clamp(true);

        // ── 3. If SVG already exists just recolour and return ──
        if (_mapSvgSelection) {
          _mapSvgSelection.selectAll('path').attr('fill', d => {
            const name  = _getStateName(d);
            const count = _mapStateMap[name];
            if (!count)   return '#e2e8f0';
            if (allSame)  return '#60a5fa';
            return colorScale(count);
          });
          return;
        }

        // ── 4. First render: build the SVG ─────────────────────
        container.innerHTML = '';
        const width  = container.clientWidth || 600;
        const height = Math.max(460, Math.round(width * 0.75));

        // Pre-compute all path strings once (avoids repeated projection calls on hover)
        const projection = d3.geoMercator().fitSize([width - 10, height - 10], geoData);
        const pathGen    = d3.geoPath().projection(projection);
        // Cache path strings keyed by feature index
        const pathCache  = geoData.features.map(f => pathGen(f));

        const svgEl = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svgEl.setAttribute('width', width);
        svgEl.setAttribute('height', height);
        svgEl.style.display = 'block';
        container.appendChild(svgEl);

        // Recreate tooltip inside container (innerHTML='' wiped the old one)
        const tooltip = document.createElement('div');
        tooltip.id = 'mapTooltip';
        tooltip.style.cssText = 'position:absolute;pointer-events:none;background:rgba(15,23,42,0.92);color:#fff;padding:8px 14px;border-radius:8px;font-size:13px;z-index:9999;display:none;box-shadow:0 4px 16px rgba(0,0,0,0.18);line-height:1.6;right:12px;top:12px;';
        container.appendChild(tooltip);

        _mapSvgSelection = d3.select(svgEl);

        // rAF throttle state for mousemove
        let _rafPending = false;
        let _pendingX, _pendingY, _pendingName, _pendingCount;

        // ── 5. Append paths using the pre-computed strings ─────
        _mapSvgSelection.selectAll('path')
          .data(geoData.features)
          .enter()
          .append('path')
          .attr('d', (_, i) => pathCache[i])        // use cache — no projection recalc
          .attr('fill', d => {
            const name  = _getStateName(d);
            const count = _mapStateMap[name];
            if (!count)  return '#e2e8f0';
            if (allSame) return '#60a5fa';
            return colorScale(count);
          })
          .attr('stroke', '#fff')
          .attr('stroke-width', 0.8)
          .style('cursor', 'pointer')
          // NO CSS transition on filter — that forced GPU composite every frame
          .on('mousemove', function(event, d) {
            const name  = _getStateName(d);
            const count = _mapStateMap[name] || 0;

            // Lighten via opacity instead of filter (cheaper, no GPU composite layer)
            if (this !== _mapSelectedEl) {
              this.style.opacity = '0.75';
            }

            // Throttle tooltip DOM writes to once per animation frame
            _pendingName  = name;
            _pendingCount = count;

            if (!_rafPending) {
              _rafPending = true;
              requestAnimationFrame(() => {
                // Pin tooltip to top-right of the map container (not cursor-relative)
                tooltip.style.cssText =
                  `display:block;position:absolute;right:12px;top:12px;left:auto;`;
                tooltip.innerHTML =
                  `<strong>${_pendingName}</strong><br>Searches:&nbsp;<strong>${_pendingCount.toLocaleString()}</strong>`;
                _rafPending = false;
              });
            }
          })
          .on('mouseleave', function() {
            tooltip.style.display = 'none';
            if (this !== _mapSelectedEl) {
              this.style.opacity = '1';
            }
          })
          .on('click', function(event, d) {
            const name = _getStateName(d);

            // Reset previous selection cheaply — just two attribute writes on one node
            if (_mapSelectedEl) {
              _mapSelectedEl.setAttribute('stroke', '#fff');
              _mapSelectedEl.setAttribute('stroke-width', '0.8');
              _mapSelectedEl.style.opacity = '1';
            }

            // Highlight new selection
            this.setAttribute('stroke', '#f59e0b');
            this.setAttribute('stroke-width', '2.5');
            this.style.opacity = '1';
            _mapSelectedEl = this;

            selectState(name);
          });
      }

      // ----------------------------------------------------------
      // selectState — drill-down panel with zero Chart.js recreate
      // ----------------------------------------------------------
      async function selectState(stateName) {
        const placeholder = document.getElementById('stateDetailPlaceholder');
        const content     = document.getElementById('stateDetailContent');
        placeholder.style.display = 'flex';
        content.style.display     = 'none';

        let data;
        try {
          const res = await fetch(`/admin/api/analytics/states/${encodeURIComponent(stateName)}`);
          data = await res.json();
        } catch (e) {
          console.error('State detail fetch failed:', e);
          placeholder.style.display = 'none';
          content.style.display     = 'flex';
          return;
        }

        // Update header
        document.getElementById('stateDetailName').textContent  = stateName;
        document.getElementById('stateDetailTotal').textContent = (data.total || 0).toLocaleString();

        // Update metric strip
        const firstOcc = data.occupations?.[0];
        if (firstOcc) {
          const title = firstOcc.title;
          document.getElementById('mapMetricTopOcc').textContent =
            title.length > 18 ? title.slice(0, 18) + '\u2026' : title;
        }

        // ── Occupation list via DocumentFragment (no innerHTML concat) ──
        const list = document.getElementById('stateOccupationList');
        list.innerHTML = '';
        if (!data.occupations?.length) {
          const empty = document.createElement('li');
          empty.style.cssText = 'font-size:12px;color:#94a3b8;text-align:center;padding:12px;';
          empty.textContent = 'No search data available for this state.';
          list.appendChild(empty);
        } else {
          const frag = document.createDocumentFragment();
          data.occupations.forEach((occ, idx) => {
            const li = document.createElement('li');
            li.style.cssText =
              `display:flex;align-items:center;gap:8px;`
              + `background:${idx === 0 ? '#eff6ff' : '#f8fafc'};`
              + `border:1px solid ${idx === 0 ? '#bfdbfe' : '#e2e8f0'};`
              + `border-radius:8px;padding:8px 10px;`;
            li.innerHTML =
              `<span style="font-size:12px;font-weight:700;color:${idx === 0 ? '#1d4ed8' : '#64748b'};min-width:18px;">${idx + 1}.</span>`
              + `<div style="flex:1;min-width:0;">`
              + `<div style="font-size:12px;font-weight:600;color:#1e293b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${occ.title}</div>`
              + `<div style="font-size:11px;color:#64748b;">${occ.count.toLocaleString()} searches\u00a0\u00b7\u00a0${occ.percentage}%</div>`
              + `</div>`
              + `<div style="width:50px;background:#e2e8f0;border-radius:4px;height:4px;">`
              + `<div style="width:${occ.percentage}%;background:#3b82f6;border-radius:4px;height:4px;"></div>`
              + `</div>`;
            frag.appendChild(li);
          });
          list.appendChild(frag);
        }

        // ── Division chart: update in-place, never destroy/recreate ──
        const divCanvas = document.getElementById('stateDivisionChart');
        const divEmpty  = document.getElementById('stateDivisionEmpty');

        if (!data.divisions?.length) {
          divCanvas.style.display = 'none';
          divEmpty.style.display  = 'block';
        } else {
          divCanvas.style.display = 'block';
          divEmpty.style.display  = 'none';

          const labels = data.divisions.map(d =>
            d.division.length > 22 ? d.division.slice(0, 22) + '\u2026' : d.division
          );
          const values = data.divisions.map(d => d.count);

          if (stateDivisionChartInstance) {
            // Update existing chart data without destroying — ~10× faster
            stateDivisionChartInstance.data.labels                   = labels;
            stateDivisionChartInstance.data.datasets[0].data         = values;
            stateDivisionChartInstance.update('none');  // 'none' skips animations
          } else {
            stateDivisionChartInstance = new Chart(divCanvas, {
              type: 'bar',
              data: {
                labels,
                datasets: [{
                  label: 'Searches',
                  data: values,
                  backgroundColor: '#6366f1',
                  borderRadius: 5,
                  borderSkipped: false,
                }]
              },
              options: {
                animation: { duration: 250 },
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                  x: { beginAtZero: true, ticks: { color: '#64748b', font: { size: 10 } } },
                  y: { ticks: { color: '#1e293b', font: { size: 10 } } }
                }
              }
            });
          }
        }

        placeholder.style.display = 'none';
        content.style.display     = 'flex';
      }
