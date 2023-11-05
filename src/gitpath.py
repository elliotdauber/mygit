import os
from enum import Enum

class GitPath(Enum):
    HEAD = "HEAD",
    MERGE_HEAD = "MERGE_HEAD",
    MERGE_MSG = "MERGE_MSG",
    MERGE_MODE = "MERGE_MODE",
    ORIG_HEAD = "ORIG_HEAD",
    CHERRY_PICK_HEAD = "CHERRY_PICK_HEAD",
    index = "index",
    heads = "refs/heads",
    log_heads = "logs/refs/heads"
    HEAD_log = "logs/HEAD"
    objects = "objects"

    @staticmethod
    def Path(gitpath, prefix=None):
        val = gitpath.value # for some reason this can either be a string or a 1-tuple
        path = os.path.join(".git", val[0] if type(val) == tuple else val)
        if prefix is not None:
            path = os.path.join(prefix, path)
        return path
    
    def BranchPath(branch_name, prefix=None):
        return os.path.join(GitPath.Path(GitPath.heads, prefix=prefix), branch_name)
    
    def BranchLogPath(branch_name, prefix=None):
        return os.path.join(GitPath.Path(GitPath.log_heads, prefix=prefix), branch_name)
    
    def ObjectPath(object_hash, prefix=None):
        object_dir = object_hash[:2]
        object_file = object_hash[2:]
        return os.path.join(GitPath.Path(GitPath.objects, prefix=prefix), object_dir, object_file)