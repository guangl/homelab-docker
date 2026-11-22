"""Reach the existing database by Docker DNS without changing Immich."""
import asyncio


async def handle(client_reader, client_writer):
    upstream_writer = None
    try:
        upstream_reader, upstream_writer = await asyncio.wait_for(
            asyncio.open_connection("immich-database", 5432), timeout=10
        )

        async def copy(reader, writer):
            while data := await reader.read(65536):
                writer.write(data)
                await writer.drain()
            if writer.can_write_eof():
                writer.write_eof()

        await asyncio.gather(
            copy(client_reader, upstream_writer), copy(upstream_reader, client_writer)
        )
    except (OSError, asyncio.TimeoutError) as error:
        print(f"PostgreSQL link: {type(error).__name__}", flush=True)
    finally:
        client_writer.close()
        if upstream_writer is not None:
            upstream_writer.close()


async def main():
    server = await asyncio.start_server(handle, "0.0.0.0", 5432)
    print("PostgreSQL link ready", flush=True)
    async with server:
        await server.serve_forever()


asyncio.run(main())
