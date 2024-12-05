import os
import asyncio

# Set LD_LIBRARY_PATH for NVIDIA library
os.environ.update({'LD_LIBRARY_PATH': '/usr/lib64-nvidia'})

async def run_process(cmd):
    print('>>> starting', *cmd)
    p = await asyncio.subprocess.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    async def pipe(lines):
        async for line in lines:
            print(line.strip().decode('utf-8'))

    await asyncio.gather(
        pipe(p.stdout),
        pipe(p.stderr),
    )

async def main():
    # Configure ngrok auth token
    await asyncio.gather(
        run_process(['ngrok', 'config', 'add-authtoken', '2co35XhoKMawCg28DqsRYbK3A8J_7krrzDFGSp8Y68Y5ne1RT'])
    )

    # Start ollama and ngrok services
    await asyncio.gather(
        run_process(['ollama', 'serve']),
        run_process(['ngrok', 'http', '--log', 'stderr', '11434', '--host-header', 'localhost:11434'])
    )

if __name__ == "__main__":
    asyncio.run(main())