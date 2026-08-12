"""Stand-in for `redis-server` when no real Redis/Docker/WSL is available.

Runs fakeredis's TcpFakeServer, which speaks the real RESP protocol over a
real TCP socket on 6379 - the app's `redis.asyncio.Redis` client (in
backend/redis_client.py) connects to it exactly as it would a real Redis
instance. This is a test-harness convenience only; it is not part of the
submission and is not required if you have real Redis available.
"""
from fakeredis import TcpFakeServer

if __name__ == '__main__':
    server_address = ('127.0.0.1', 6379)
    server = TcpFakeServer(server_address, server_type='redis')
    print(f'fakeredis listening on {server_address[0]}:{server_address[1]}')
    server.serve_forever()
