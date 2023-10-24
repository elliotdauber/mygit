import hashlib
import os
import struct
from log import Log
import binascii
import zlib
import re
from index import Index
from commit import Commit

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def sha1hash(content):
    hasher = hashlib.sha1()
    hasher.update(content)
    return hasher.hexdigest()

def sha1hash_bytes(content):
    hasher = hashlib.sha1()
    hasher.update(content)
    return hasher.digest()

def files_in_current_dir():
    # TODO: don't hardcode this
    ignores = [".DS_Store", ".git"]
    fileList = []
    def clean_path(path):
        if path.startswith("./"):
            path = path[2:]
        return path

    def files_in_dir_rec(dirToScan):
        for entry in os.scandir(dirToScan):
            entry_path = clean_path(entry.path)
            if entry_path in ignores: continue
            if entry.is_file():
                fileList.append(entry_path)
            elif entry.is_dir():
                files_in_dir_rec(entry_path)
            # print(entry.stat())
    files_in_dir_rec(os.curdir)
    return fileList

def current_branch():
    HEAD_file = os.path.join(".git", "HEAD")
    with open(HEAD_file, "r") as f:
        while True:
            line = f.readline().strip()
            if line.startswith("ref: "):
                ref = line.split("ref: ")[1]
                return ref.split("/")[-1]
            if line is None:
                break
    return None

def all_branches():
    heads_folder = os.path.join(".git", "refs", "heads")
    branches = []
    for root, dirs, files in os.walk(heads_folder):
        for file in files:
            branch = os.path.relpath(os.path.join(root, file), heads_folder)
            branches.append(branch)
    return sorted(branches)

def file_in_dir(filepath, dirpath):
    filepath_dir = "/".join(filepath.split("/")[:-1])
    return filepath_dir == dirpath

# returns the hash of the content (name of object file)
def write_object_file(content):
    sha1_hash = sha1hash(content)
    objects_dir = os.path.join(".git", "objects")

    objects_subdir = os.path.join(objects_dir, sha1_hash[:2])
    if not os.path.exists(objects_subdir):
        os.mkdir(objects_subdir)
    object_file = os.path.join(objects_subdir, sha1_hash[2:])

    if not os.path.exists(object_file):
        # compress and write
        db_object_compressed = zlib.compress(content)
        with open(object_file, "wb") as f:
            f.write(db_object_compressed)

    return sha1_hash

def read_object_file(object_hash):
    objects_dir = os.path.join(".git", "objects")
    objects_subdir = os.path.join(objects_dir, object_hash[:2])
    object_file = os.path.join(objects_subdir, object_hash[2:])
    object_compressed = b""
    with open(object_file, "rb") as f:
        object_compressed = f.read()
    return zlib.decompress(object_compressed)


# dirpath should be "" for the root dir, and should have a trailing "/" for all other dirs
def create_tree(index, dirpath=""):
    nodes = []
    subdirs_visited = set()
    for entry in index.entries:
        filepath = entry.getFilepathStr()
        if file_in_dir(filepath, dirpath):
            filename = filepath.split("/")[-1]
            node = (f"100644 {filename}\0").encode('utf-8') + binascii.unhexlify(entry.getSha1Str().encode('utf-8'))
            nodes.append(node)
        elif filepath.startswith(dirpath):
            # this file is in the current dirpath (any number of levels deep)
            # get next subdir, make a tree from it if there is none yet
            is_root_dir = dirpath == ""
            subdir_name = filepath[len(dirpath) + (0 if is_root_dir else 1):].split("/")[0]
            subdir = dirpath + ("" if is_root_dir else "/") + subdir_name
            # Log.Debug(f"found subdir {subdir}")
            if subdir not in subdirs_visited:
                subdirs_visited.add(subdir)
                subtree_hash = create_tree(index, subdir)
                # Log.Debug(f"hash for {subdir}: {subtree_hash}")
                node = (f"40000 {subdir_name}\0").encode('utf-8') + binascii.unhexlify(subtree_hash.encode('utf-8'))
                nodes.append(node)
    content = b"".join(nodes)
    # Log.Debug(f"content for {dirpath}: {content}")
    header = f"tree {len(content)}\0"
    header_encoded = header.encode('utf-8')
    
    tree = header_encoded + content
    # Log.Debug(f"tree for {dirpath}: {tree}")
    return write_object_file(tree)
    # Log.Debug(f"tree for {dirpath}: {tree}")

# returns (hash, ambigious?)
def commit_hash_from_ref(ref):
    parts = ref.split("/")
    ref_types = ["tags", "heads", "remotes"]
    
    # TODO: make this work for refs/stash or just stash
    
    # if this is a full ref, resolve it
    if parts[0] == "refs" and len(parts) >= 3:
        full_path = os.path.join(".git", ref)
        if os.path.exists(full_path):
            with open(full_path, "r") as f:
                return (f.read().strip(), False)
        return (None, False)

    # if the ref starts with a ref_type, prepend "refs/" and recursively resolve
    if parts[0] in ref_types and len(parts) >= 2:
        return (commit_hash_from_ref(f"refs/{ref}"), False)
    
    # otherwise, this is a bare ref, try prepending each ref type and recursively resolve
    # if more than one ref_type matches, mark as ambiguous
    possible_hashes = []
    for ref_type in ref_types:
        commit_hash = commit_hash_from_ref(f"refs/{ref_type}/{ref}")[0]
        if commit_hash is not None:
            possible_hashes.append(commit_hash)
    
    if len(possible_hashes) > 0:
        return (possible_hashes[0], len(possible_hashes) > 1)
    return (None, False)

def is_valid_hash(s):
    return re.compile(r'^[0-9a-f]{40}$').match(s)

def shortened_hash(s):
    return s[:7] if is_valid_hash(s) else s

def update_ORIG_HEAD(s):
    ORIG_HEAD_file = os.path.join(".git", "ORIG_HEAD")
    with open(ORIG_HEAD_file, "w") as f:
        f.write(s)

def update_files_to_commit_hash(commit_hash):
    index_file = os.path.join(".git", "index")
    current_index = Index.FromFile(index_file)
    new_commit = Commit.FromHash(commit_hash)
    new_tree = new_commit.getTree()
    new_tree_files = new_tree.getFiles()

    # Create/update files that are in the branch being switched to but are not in the current branch
    for filepath, blob in new_tree_files.items():
        Log.Debug(f"{filepath}, {blob.sha1}")
        index_entry = current_index.getEntryWithFilepath(filepath)
        if index_entry is None or index_entry.getSha1Str() != blob.sha1:
            # This file is not in the current index, so it needs to be created
            intermediate_dirs = "/".join(filepath.split("/")[:-1])
            if intermediate_dirs != "":
                os.makedirs(intermediate_dirs, exist_ok=True)
            with open(filepath, "w") as f:
                f.write(blob.content)

    # Delete files that are in the current branch but not in the branch being switched to
    # TODO: right now, "added" files are deleted when switching to a new branch
    for entry in current_index.entries:
        filepath = entry.getFilepathStr()
        if filepath not in new_tree_files.keys():
            os.remove(filepath)
            # Delete intermediate folders that are now empty
            intermediate_dirs = "/".join(filepath.split("/")[:-1])
            if intermediate_dirs != "":
                os.removedirs(intermediate_dirs)

    new_index = Index.FromTree(new_tree)
    new_index.writeToFile(index_file)
    # new_index.print()

def myers_diff(s1, s2):
    n = len(s1)
    m = len(s2)
    MAX = n + m

    v = [0 for _ in range(-MAX, MAX + 1)]
    V = []
    v[1] = 0

    found = False
    for d in range(MAX+1):
        Log.Debug(f"d = {d}")
        for k in range(-d, d+1, 2):
            Log.Debug(f"k = {k}, v[k-1] = {v[k-1]}, v[k+1] = {v[k+1]}")
            if k == -d or (k != d and v[k-1] < v[k+1]):
                x = v[k+1]
            else:
                x = v[k-1] + 1
            
            y = x - k

            Log.Debug(f"checking if s1[{x}] == s2[{y}]")
            while x < n and y < m and s1[x] == s2[y]:
                Log.Debug(f"incrementing x and y")
                x, y = x+1, y+1

            Log.Debug(f"assigning v[{k}] = {x}")
            v[k] = x

            found = x >= n and y >= m
            if found: break
        
        V.append(v.copy())
        if found:
            Log.Debug(f"found d: {d}")
            return myers_diff_get_path(s1, s2, V)
    # theoretically not possible:
    return None

def myers_diff_get_path(s1, s2, V):
    x, y = len(s1), len(s2)
    points = []
    for d in reversed(range(len(V) - 1)):
        v = V[d]
        k = x - y
        Log.Debug(f"d={d}, k={k}, x={x}, y={y}")

        if k == -d or (k != d and v[k - 1] < v[k + 1]):
            prev_k = k + 1
        else:
            prev_k = k - 1
        prev_x = v[prev_k]
        prev_y = prev_x - prev_k
        
        while x > prev_x and y > prev_y:
            points.append((x, y))
            x, y = x - 1, y - 1
        points.append((x, y))

        x, y = prev_x, prev_y

    points.reverse()

    # add any necessary points on the diagonal at the beginning of the sequence
    first_pt = points[0]
    new_pt = min(first_pt[0], first_pt[1])
    while new_pt >= 0:
        points.insert(0, (new_pt, new_pt))
        new_pt -= 1

    Log.Debug(points)
    
    trace = []
    for i in range(len(points) - 1):
        point_start = points[i]
        point_end = points[i+1]
        x_start, y_start = point_start
        x_end, y_end = point_end
        dx, dy = x_end - x_start, y_end - y_start
        if dx == dy:
            trace.append("M")
        elif dx > dy:
            trace.append("D")
        else:
            trace.append("A")

    return trace


# def myers_path_rec(s1, s2, V, d, k):
#     v = V[d]
#     x = v[k]
#     y = x - k
#     print(f"d={d}, k={k}, x={x}, y={y}")
    
#     if d == 0:
#         print("done!")
#         print((0, 0), (x, y))
#     else:
#         while s1[x - 1] == s2[y - 1]:
#             print(f"{s1}[{x-1}] = {s1[x-1]}, {s2}[{y-1}] = {s2[y-1]}")
#             x, y = x-1, y-1

#         print(x, y)

#         # assume this was a down move, check if true
#         d_prev = d - 1
#         v_prev = V[d_prev]
#         k_prev = k# + 1
#         # print(f"d_prev={d_prev}, k_prev={k_prev}, \nv_prev={v_prev}, \nv={v}")
#         down = k_prev == -d_prev or (k_prev != d_prev and v_prev[k_prev-1] < v_prev[k_prev+1])
#         print(down)
#         x_start, y_start = x, y
#         if down:
#             y_start -= 1
#         else:
#             x_start -= 1
#         myers_path_rec(s1, s2, V, d-1, x_start - y_start)