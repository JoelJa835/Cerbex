import urllib3

http = urllib3.PoolManager()
r = http.request('GET', 'https://httpbin.org/get')
print(r.status)
