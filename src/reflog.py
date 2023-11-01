from gitpath import GitPath
from commit import Commit
import os
import utils

class Reflog: 
    # branch_name should be None if the line should only be written to HEAD   
    @staticmethod
    def WriteLogLine(prev_commit_hash, new_commit_hash, data, branch_name=None):
        if prev_commit_hash is None:
            prev_commit_hash = '0'*40

        log_line = f"{prev_commit_hash} {new_commit_hash} {utils.signature()}	{data}\n"

        if branch_name is not None:
            log_file = GitPath.BranchLogPath(branch_name)
            utils.create_intermediate_dirs(log_file)
            with open(log_file, 'a') as f:
                f.write(log_line)

        if branch_name is None or utils.current_branch() == branch_name:
            with open(GitPath.Path(GitPath.HEAD_log), "a") as f:
                f.write(log_line)

    @staticmethod
    def DeleteLog(branch_name):
        log_file = GitPath.BranchLogPath(branch_name)
        if os.path.exists(log_file):
            os.remove(log_file)
        # TODO: delete any now-empty log dirs
    
    @staticmethod
    def Commit(branch_name, commit_hash):
        commit = Commit.FromHash(commit_hash)
        parent_commit = commit.getParentHash()
        Reflog.WriteLogLine(parent_commit, commit_hash, f"commit{' (initial)' if not parent_commit else ''}: {commit.message}", branch_name=branch_name)

    @staticmethod
    def CreateBranch(branch_name, from_ref):
        Reflog.WriteLogLine(None, utils.commit_hash_from_ref(branch_name)[0], f"branch: Created from {from_ref}", branch_name=branch_name)

    @staticmethod
    def Reset(branch_name, prev_commit_hash, new_commit_hash, rev):
        Reflog.WriteLogLine(prev_commit_hash, new_commit_hash, f"reset: moving to {rev}", branch_name=branch_name)

    @staticmethod
    def Checkout(prev_commit_hash, new_commit_hash, prev_rev, new_rev):
        Reflog.WriteLogLine(prev_commit_hash, new_commit_hash, f"checkout: moving from {prev_rev} to {new_rev}")