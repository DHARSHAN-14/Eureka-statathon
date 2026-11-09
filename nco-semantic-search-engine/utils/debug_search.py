import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import importlib.util
spec = importlib.util.spec_from_file_location('searchapp', os.path.join(os.path.dirname(__file__), '..', 'scripts', '06_searchapp.py'))
search_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(search_module)

# Test 'star' query specifically
results = search_module.search('star')
print(f'Query: star')
print(f'Number of results: {len(results)}')
if results and len(results) >= 2:
    top_result = results[0]
    next_result = results[1]
    top_score = top_result.get('final_score', 0)
    next_score = next_result.get('final_score', 0)
    print(f'Top result: {top_result.get("occupation_title", "N/A")}')
    print(f'Top score: {top_score:.3f}')
    print(f'Next result: {next_result.get("occupation_title", "N/A")}')
    print(f'Next score: {next_score:.3f}')
    print(f'Score difference: {abs(top_score - next_score):.3f}')
    print(f'First condition (top < 0.6 and diff < 0.05): {top_score < 0.6 and abs(top_score - next_score) < 0.05}')
    print(f'Second condition (top < 0.5): {top_score < 0.5}')
else:
    print('Not enough results')
