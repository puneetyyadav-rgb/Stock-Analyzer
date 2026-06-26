import os

def tree(path, prefix=''):
    items = [x for x in sorted(os.listdir(path)) if x not in ('node_modules', '.git', '__pycache__', '.pytest_cache', 'venv', 'env', '.env', 'tree.py')]
    for i, x in enumerate(items):
        is_last = (i == len(items) - 1)
        print(prefix + ('`-- ' if is_last else '|-- ') + x)
        p = os.path.join(path, x)
        if os.path.isdir(p):
            tree(p, prefix + ('    ' if is_last else '|   '))

tree('.')
