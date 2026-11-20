import asyncio
import os
import sys
import httpx
import glob

URL = "https://huggingface.co/Systran/faster-whisper-small/resolve/main/model.bin"
TOTAL_SIZE = 483546902
BLOB_DIR = os.path.expanduser("~/.cache/huggingface/hub/models--Systran--faster-whisper-small/blobs")
FINAL_FILE = os.path.join(BLOB_DIR, "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671")
NUM_CHUNKS = 8

async def download_range(client, start, end, chunk_id, temp_path):
    headers = {"Range": f"bytes={start}-{end}"}
    for attempt in range(5):
        try:
            async with client.stream("GET", URL, headers=headers, timeout=60.0) as resp:
                if resp.status_code in [200, 206]:
                    with open(temp_path, "wb") as f:
                        async for chunk in resp.aiter_bytes(chunk_size=65536):
                            f.write(chunk)
                    print(f" Chunk {chunk_id} ({start}-{end}) downloaded successfully.")
                    return
        except Exception as e:
            print(f"Retry chunk {chunk_id} (attempt {attempt+1}): {e}")
            await asyncio.sleep(1)
    raise RuntimeError(f"Failed chunk {chunk_id}")

async def main():
    os.makedirs(BLOB_DIR, exist_ok=True)
    chunk_size = TOTAL_SIZE // NUM_CHUNKS
    tasks = []
    temp_files = []

    print(f"Starting parallel download of {TOTAL_SIZE / (1024*1024):.1f} MB across {NUM_CHUNKS} streams...")
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for i in range(NUM_CHUNKS):
            start = i * chunk_size
            end = (start + chunk_size - 1) if i < NUM_CHUNKS - 1 else (TOTAL_SIZE - 1)
            t_path = f"{FINAL_FILE}.part{i}"
            temp_files.append(t_path)
            tasks.append(download_range(client, start, end, i, t_path))
        
        await asyncio.gather(*tasks)

    print("All chunks downloaded. Assembling final model.bin...")
    with open(FINAL_FILE, "wb") as outfile:
        for t_path in temp_files:
            with open(t_path, "rb") as infile:
                while True:
                    data = infile.read(1024 * 1024)
                    if not data:
                        break
                    outfile.write(data)
            os.remove(t_path)

    # Link to snapshot
    snapshot_dirs = glob.glob(os.path.expanduser("~/.cache/huggingface/hub/models--Systran--faster-whisper-small/snapshots/*"))
    for s_dir in snapshot_dirs:
        link_target = os.path.join(s_dir, "model.bin")
        if os.path.exists(link_target) or os.path.islink(link_target):
            os.remove(link_target)
        os.symlink(FINAL_FILE, link_target)
        print(f"Linked {FINAL_FILE} -> {link_target}")

    print("Model ready!")

if __name__ == "__main__":
    asyncio.run(main())
