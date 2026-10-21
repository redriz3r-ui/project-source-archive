"""Only safe cache directives and security-header presence enter the report."""
import re

def inspect_headers(headers):
 cache=headers.get('cache-control','').lower()
 flags=[x for x in ['no-store','no-cache','public','private','immutable','must-revalidate'] if re.search(r'(?:^|[,\s])'+re.escape(x)+r'(?:$|[,\s])',cache)]
 maxage=re.search(r'(?:^|[,\s])max-age=(\d{1,10})(?:$|[,\s])',cache)
 if maxage: flags.append('max-age='+maxage[1])
 security=[h for h in ['strict-transport-security','content-security-policy','x-content-type-options','x-frame-options','referrer-policy','permissions-policy'] if h in headers]
 return flags,security
