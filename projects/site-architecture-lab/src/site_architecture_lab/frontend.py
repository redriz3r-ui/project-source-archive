"""Resource roles are observable; framework and initialization internals remain unknown."""
import re

def asset_kind(path,mime):
 if mime in {'application/javascript','text/javascript','text/css'} or path.endswith(('.js','.css')): return 'frontend'
 if mime=='application/json' or re.search(r'/(api|graphql)(/|$)',path): return 'api'
 if mime=='text/html': return 'document'
 return 'other'
