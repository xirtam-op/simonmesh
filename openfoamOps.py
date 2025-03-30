import os
import json
import asyncio
import subprocess
from pathlib import Path
from toDICT import *
import re
# import matplotlib.pyplot as plt
import io
import base64

async def parse_bc_name(part):
    reverse_ = part[::-1]
    for line in reverse_:
        if len(line.strip()) > 1:
            return line.strip()
    return ""
    
async def parse_bc_info(part):
    type_ = ""
    nFaces_ = ""
    startFace_ = ""
    
    for line in part:
        if line.find("type") >= 0 and line.find(';') > 0:
            line = line[0:line.find(';')];
            result = re.split(r'[\t ]+', line)
            type_ = result[-1]
            
        if line.find("nFaces") >= 0 and line.find(';') > 0:
            line = line[0:line.find(';')];
            result = re.split(r'[\t ]+', line)
            nFaces_ = result[-1]
            
        if line.find("startFace") >= 0 and line.find(';') > 0:
            line = line[0:line.find(';')];
            result = re.split(r'[\t ]+', line)
            startFace_ = result[-1]
            
    return type_, nFaces_, startFace_

async def parse_boundary_file(file_path):
    boundaries = []
    with open(file_path, 'r') as file:
        content = file.readlines()

    check_ = -1
    for index_, l in enumerate(content):
        if l.find('{') >= 0:
            start_ = index_
        if l.find('}') >= 0:
            end_ = index_

            if (check_ > start_ and end_ > check_):
                type_, *_ = await parse_bc_info(content[start_:end_ + 1])
                name_ = await parse_bc_name(content[start_ - 5:start_ + 1])
                boundaries.append({"name":name_, "type":type_})
        
        if l.find('type') > 0:
            check_ = index_
        
    return boundaries


async def websocket_send(websocket, message):
    await websocket.send(json.dumps(message))

async def run_command(command):
    """Run a command and return its output."""
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Command failed with error: {e}")
        return ""
    except FileNotFoundError:
        print("Docker command not found. Is Docker installed?")
        return ""

async def run_linux_command(command):
    '''Run a command on Linux ruuning on docker and return its output.'''
    # docker exec meshos /bin/bash -c "source /usr/lib/openfoam/openfoam2406/etc/bashrc
    print("command: ", command)
    if os.name == 'nt':
        try:
            dCommand_ = ['docker', 'exec', 'meshos', '/bin/bash', '-c', f'source /usr/lib/openfoam/openfoam2406/etc/bashrc && {command}']
            # dCommand_ = ['docker', 'exec', 'meshos', '/bin/bash', '-c', f'{command}']
            print(' '.join(dCommand_))
            result = subprocess.run(dCommand_, capture_output=True, text=True, check=True)
            print(result.stdout)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(f"Command failed with error: {e}")
            return ""
        except FileNotFoundError:
            print("Docker command not found. Is Docker installed?")
            return ""
    elif os.name == 'posix':
        result = subprocess.run(command, 
                                capture_output=True, 
                                text=True, check=True,
                                shell=True)
        return result.stdout.strip()
    else:
        print('Linux command: ', command)
    
async def openfoamServer(obj, blockMeshObj, base_dir,case_dir, websocket, connected_clients):
    print("openfoamServer: ", obj, "ops" in obj)
    if not "ops" in obj:
        return {"status": "faile", "message": "No ops in the request."}
    ops = obj["ops"]
    if ops == 'view':
        blockMeshDict = ToMeshDICT(blockMeshObj, os.path.join(case_dir, 'octopus.dict'))
        blockMeshDict.write()
        controlDict = ToControlDICT(os.path.join(case_dir, 'system', 'controlDict'))
        controlDict.write()

        # Convert from windows path to linux path
        if os.name == 'nt':
            base_ = Path(base_dir)
            case_ = Path(case_dir)
            relative_path = case_.relative_to(base_)
            relative_path_linux = relative_path.as_posix()
            case_linux = os.path.join('/OpenFOAM', relative_path_linux)
        
            await run_linux_command(f'cd /OpenFOAM && blockMesh -case {relative_path_linux} -dict octopus.dict')

            patches = obj["para"]
            print('server patches: ', patches)
            for patch in patches:
                print(patch)
                patchName = patch["name"]
                # Checking under windows
                patchPath = os.path.join(case_dir, f'{patchName}.vtk')

                if os.path.exists(patchPath):
                    os.remove(patchPath)

                await run_linux_command(f'cd /OpenFOAM && surfaceMeshExtract -case {relative_path_linux} -patches "{patchName}" {patchName}.vtk')

            await run_linux_command(f'cd /OpenFOAM && surfaceMeshExtract -case {relative_path_linux} -patches "walls" walls.vtk')

            print("before patches: ", patches)
            patches.append({"name": "walls"})
            print("after patches: ", patches)

            # surfaceMeshExtract -case {relative_path_linux} '(patch)' patchName.vtk 
            # objOutput = await run_linux_command(f'cd /OpenFOAM && surfaceMeshExtract -case {relative_path_linux} surfaceMesh.vtk')
            
            for patch in patches:
                patchName = patch["name"]
                objPath = os.path.join(case_dir, f'{patchName}.vtk')
                if os.path.exists(objPath):
                    await websocket_send(websocket, {"name": patchName, "target": "ofMesh", 
                    "status": "success",
                    "ops": "view", "url": objPath})
                    '''
                    chunkSize = 64 * 1024 # 64KB chunk size
                    with open(objPath, 'rb') as f:
                        while chunk := f.read(chunkSize):
                            await websocket.send(chunk)
                    await websocket.send(b'__END__')
                    print(f'Sent chunk of size {len(chunk)} bytes')
                    '''
                    print("objFile sent to client successfully")
            
            CHUNK_SIZE = 1024 * 64  # 64 KB per chunk
            for patch in patches:
                patchName = patch["name"]
                objPath = os.path.join(case_dir, f'{patchName}.vtk')
                if os.path.exists(objPath):
                    file_size = os.path.getsize(objPath)
                    total_chunks = (file_size // CHUNK_SIZE) + (1 if file_size % CHUNK_SIZE else 0)

                    await websocket.send(f"__START__:{patchName}:{total_chunks}")

                    with open(objPath, "rb") as f:
                        for _ in range(total_chunks):
                            chunk = f.read(CHUNK_SIZE)
                            await websocket.send(chunk)
                            await asyncio.sleep(0.01)  # Allow time for transmission

                    await websocket.send("__END__")  # Mark file transfer complete

        elif os.name == 'posix':
            await run_linux_command(f'cd {case_dir} && blockMesh -case {case_dir} -dict octopus.dict')
            objOutput = await run_linux_command(f'cd {case_dir} && surfaceMeshExtract -case {case_dir} surfaceMesh.vtk')
            print("openfoamOps: ", ops, " success!")
            print(objOutput)

            patches = obj["para"]
            print('server patches: ', patches)
            for patch in patches:
                print(patch)
                patchName = patch["name"]
                # Checking under windows
                patchPath = os.path.join(case_dir, f'{patchName}.vtk')

                if os.path.exists(patchPath):
                    os.remove(patchPath)

                await run_linux_command(f'cd {case_dir} && surfaceMeshExtract -case {case_dir} -patches "{patchName}" {patchName}.vtk')

            await run_linux_command(f'cd {case_dir} && surfaceMeshExtract -case {case_dir} -patches "walls" walls.vtk')

            print("before patches: ", patches)
            patches.append({"name": "walls"})
            print("after patches: ", patches)

            for patch in patches:
                patchName = patch["name"]
                objPath = os.path.join(case_dir, f'{patchName}.vtk')
                if os.path.exists(objPath):
                    await websocket_send(websocket, {"name": patchName, "target": "ofMesh", 
                    "status": "success",
                    "ops": "view", "url": objPath})
                    '''
                    chunkSize = 64 * 1024 # 64KB chunk size
                    with open(objPath, 'rb') as f:
                        while chunk := f.read(chunkSize):
                            await websocket.send(chunk)
                    await websocket.send(b'__END__')
                    print(f'Sent chunk of size {len(chunk)} bytes')
                    '''
                    print("objFile sent to client successfully")

            CHUNK_SIZE = 1024 * 64  # 64 KB per chunk
            for patch in patches:
                patchName = patch["name"]
                objPath = os.path.join(case_dir, f'{patchName}.vtk')
                if os.path.exists(objPath):
                    file_size = os.path.getsize(objPath)
                    total_chunks = (file_size // CHUNK_SIZE) + (1 if file_size % CHUNK_SIZE else 0)

                    await websocket.send(f"__START__:{patchName}:{total_chunks}")

                    with open(objPath, "rb") as f:
                        for _ in range(total_chunks):
                            chunk = f.read(CHUNK_SIZE)
                            await websocket.send(chunk)
                            await asyncio.sleep(0.01)  # Allow time for transmission

                    await websocket.send("__END__")  # Mark file transfer complete

        else:
            print("Later")
            await websocket_send(websocket, {"name": "server", "target": "ofMesh", 
                "status": "fail",
                "ops": "create"})
            
        '''
        objPath = os.path.join(case_dir, 'surfaceMesh.vtk')
        if os.path.exists(objPath):
            await websocket_send(websocket, {"name": "server", "target": "ofMesh", 
            "status": "success",
            "ops": "view", "url": objPath})

            chunkSize = 64 * 1024 # 64KB chunk size
            with open(objPath, 'rb') as f:
                while chunk := f.read(chunkSize):
                    await websocket.send(chunk)
            await websocket.send(b'__END__')
            print(f'Sent chunk of size {len(chunk)} bytes')
            print("objFile sent to client successfully")
        else:
            print("openfoamOps: ", ops, " not found")
            await websocket_send(websocket, {"name": "server", "target": "ofMesh", 
                "status": "fail",
                "ops": "view"})
        '''
        
        return

    if ops == 'extract':

        boundary_file = os.path.join(case_dir, 'constant', 'polyMesh', 'boundary')
        if not os.path.exists(boundary_file):
            await websocket_send(websocket, {"name": "server", "target": "ofMesh", 
                "status": "fail",
                "ops": "extract"})
            return
        boundary_dict = await parse_boundary_file(os.path.join(case_dir, 'constant', 'polyMesh', 'boundary'))
        print('boundary_dict: ', boundary_dict)
        if os.name == 'nt':
            base_ = Path(base_dir)
            case_ = Path(case_dir)
            relative_path = case_.relative_to(base_)
            relative_path_linux = relative_path.as_posix()
            case_linux = os.path.join('/OpenFOAM', relative_path_linux)

            print('server patches: ', boundary_dict)
            for patch in boundary_dict:
                patchName = patch["name"]
                # Checking under windows
                patchPath = os.path.join(case_dir, f'{patchName}.vtk')

                if os.path.exists(patchPath):
                    os.remove(patchPath)

                await run_linux_command(f'cd /OpenFOAM && surfaceMeshExtract -case {relative_path_linux} -patches "{patchName}" {patchName}.vtk')

            CHUNK_SIZE = 1024 * 64  # 64 KB per chunk
            for patch in boundary_dict:
                patchName = patch["name"]
                objPath = os.path.join(case_dir, f'{patchName}.vtk')
                if os.path.exists(objPath):
                    file_size = os.path.getsize(objPath)
                    total_chunks = (file_size // CHUNK_SIZE) + (1 if file_size % CHUNK_SIZE else 0)

                    await websocket.send(f"__START__:{patchName}:{total_chunks}")

                    with open(objPath, "rb") as f:
                        for _ in range(total_chunks):
                            chunk = f.read(CHUNK_SIZE)
                            await websocket.send(chunk)
                            await asyncio.sleep(0.01)  # Allow time for transmission

                    await websocket.send("__END__")  # Mark file transfer complete
        
    if ops == 'monitor':
        print('process log file: ', obj)
        runLogName = obj["para"]["run"] or "log.run" 
        log_file = os.path.join(case_dir, runLogName)
        print('log_file: ', log_file)
        patterns = {
            "Ux": re.compile(r"Solving for Ux, Initial residual = ([\d.eE+-]+)"),
            "Uy": re.compile(r"Solving for Uy, Initial residual = ([\d.eE+-]+)"),
            "Uz": re.compile(r"Solving for Uz, Initial residual = ([\d.eE+-]+)"),
            "p": re.compile(r"Solving for p, Initial residual = ([\d.eE+-]+)"),
            "continuity": re.compile(r"continuity errors : .* global = ([\d.eE+-]+)"),
            "time": re.compile(r"^Time = ([\d.eE+-]+)")
        }
        
        residuals = {key: [] for key in patterns}

        count = {key: 0 for key in patterns}

        # Function to process a line of the log file
        def process_line(line):
            global count
            for key, pattern in patterns.items():
                match = pattern.search(line)
                if match:
                    value_ = float(match.group(1))
                    if key == "time":
                        count = {ki: 0 for ki in patterns}
                        logValue = value_
                    else:
                        logValue = np.log10(np.abs(value_)) * np.sign(value_)
                    if count[key] == 0:
                        residuals[key].append(logValue)
                        count[key] += 1
        
        # Read existing data in the log file
        if os.path.exists(log_file):
            with open(log_file, 'r') as file:
                for line in file:
                    process_line(line)

        if any(residuals[key] for key in residuals):
            # Generate the plot and send it as a base64-encoded image
            # print("Sending plot data...")
            # plot_data = generate_plot()
            # await websocket.send(json.dumps({"plot": plot_data}))
            await websocket.send(json.dumps(residuals))
            for key in residuals:
                residuals[key].clear()

        running = True
        # Tail the log file
        while running:

            try:
                with open(log_file, 'r') as file:
                    file.seek(0, 2)
                    while running:
                        line = file.readline()
                        if line:
                            process_line(line)
                            if any(residuals[key] for key in residuals):
                                await websocket.send(json.dumps(residuals))
                                for key in residuals:
                                    residuals[key].clear()
                        else:
                            await asyncio.sleep(1)

                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=0.1)
                            print(f"Received message in inner loop: {message}")
                            if message == "stop":
                                print("Received 'stop' command. Exiting loop.")
                                running = False
                        except asyncio.TimeoutError:
                            pass  # No message received, continue looping
                        
            except FileNotFoundError:
                print("Log file not found. Retrying in 5 seconds...")
                await asyncio.sleep(5)
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(5)


            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=0.1)
                print(f"Received message in outer loop: {message}")
                if message == "stop":
                    print("Received 'stop' command. Exiting loop.")
                    running = False
            except asyncio.TimeoutError:
                pass  # No message received, continue looping

