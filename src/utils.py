import hashlib
import os
import struct
from log import Log
import binascii
import zlib

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
