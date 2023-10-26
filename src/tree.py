import utils
import binascii
import os

class Blob:
    def __init__(self, sha1, content):
        self.sha1 = sha1
        self.content = content

    def print(self):
        print(self.content, end="")

    @staticmethod
    def FromHash(blob_hash):
        object_decompressed = utils.read_object_file(blob_hash)
        object_decoded = object_decompressed.decode('utf-8', 'replace')
        object_text = object_decoded.split("\0")[1]
        return Blob(blob_hash, object_text)

class Tree:
    class TreeNode:
        def __init__(self, mode, sha1, path):
            self.mode = mode
            self.sha1 = sha1
            self.path = path

        def toTree(self):
            return Tree.FromHash(self.sha1, self.path)

    class BlobNode:
        def __init__(self, mode, sha1, path):
            self.mode = mode
            self.sha1 = sha1
            self.path = path

        def toBlob(self):
            return Blob.FromHash(self.sha1)

    def __init__(self, sha1, nodes):
        self.sha1 = sha1
        self.nodes = nodes

    def getNodesExpanded(self):
        expanded_nodes = {}
        for node in self.nodes:
            if type(node) == Tree.TreeNode:
                expanded_nodes[node.path] = node.toTree()
            elif type(node) == Tree.BlobNode:
                expanded_nodes[node.path] = node.toBlob()
        return expanded_nodes
    
    # get leaf blobs up through depth levels deep
    # if depth == -1, gets all leaf blobs
    # returns dict of form filepath (str): Blob
    def getFiles(self, depth=-1):
        files = {}
        for node in self.nodes:
            if type(node) == Tree.BlobNode:
                files[node.path] = Blob.FromHash(node.sha1)
            elif type(node) == Tree.TreeNode:
                if depth != 0:
                    subfiles = Tree.FromHash(node.sha1, node.path).getFiles(depth - 1 if depth != -1 else -1)
                    # TODO: are paths here full?
                    files.update(subfiles)
        return files

    def print(self):
        for node in self.nodes:
            print(f"{node.mode} {'blob' if type(node) == Tree.BlobNode else 'tree'} {node.sha1}    {node.path}")

    # def applyDiff(self, diff):
    #     new_tree = Tree()
    #     files_in_tree = self.getFiles()
    #     for file_diff in diff.getFileDiffs():
    #         pass
    #     return newTree

    @staticmethod
    def FromWorkingDir():
        # TODO: implement
        print('unimplemented')
        exit(1)
        
        # TODO: walk the current dir, build up the tree just as we would do with an Index
        # Maybe it's easiest to make an Index from the working dir, or maybe this is messy
        # Could be time for a refactor to make this possible cleanly
        all_files = sorted(utils.files_in_current_dir())
        print(all_files)
        return Tree("", [])

    @staticmethod
    def FromHash(tree_hash, tree_dir=""):
        object_decompressed = utils.read_object_file(tree_hash)
        # adding each new file seems to increase the number at the front by 28 + filepath length
        # Log.Debug(object_decompressed)
        bytes_so_far = len("tree ")

        tree_numbytes_str = object_decompressed[bytes_so_far:].split(b"\x00")[0].decode('utf-8')
        bytes_so_far += len(tree_numbytes_str) + 1
        tree_numbytes = int(tree_numbytes_str)

        # Log.Debug(f"found a tree with {tree_numbytes} bytes")
        header_len = bytes_so_far
        nodes = []

        while bytes_so_far < tree_numbytes + header_len:
            entry_mode = object_decompressed[bytes_so_far:].split(b" ")[0].decode('utf-8')
            bytes_so_far += len(entry_mode) + 1

            entry_filepath = object_decompressed[bytes_so_far:].split(b'\x00')[0].decode('utf-8')
            bytes_so_far += len(entry_filepath) + 1

            hash_len = 20
            entry_hash_raw = object_decompressed[bytes_so_far:bytes_so_far + hash_len]
            entry_hash = binascii.hexlify(entry_hash_raw).decode('utf-8')
            bytes_so_far += hash_len

            if entry_mode == '100644':
                nodes.append(Tree.BlobNode(entry_mode.zfill(6), entry_hash, os.path.join(tree_dir, entry_filepath)))
            elif entry_mode == '40000':
                nodes.append(Tree.TreeNode(entry_mode.zfill(6), entry_hash, os.path.join(tree_dir, entry_filepath)))
            # TODO: handle other modes
        
        return Tree(tree_hash, nodes)