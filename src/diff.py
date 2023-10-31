from log import Log
from commit import Commit
from tree import Tree
import utils
from enum import Enum

class DiffTraceAction(Enum):
    DELETE = 1
    ADD = 2
    MATCH = 3

class FileDiff:
    def __init__(self, base_blob, base_filepath, target_blob, target_filepath):
        self.base_filepath = base_filepath
        self.target_filepath = target_filepath
        self.base_blob = base_blob
        self.target_blob = target_blob

        (self.base_lines, self.target_lines) = self.__content_lines()

        self.trace = FileDiff.MyersDiff(self.base_lines, self.target_lines)

    # returns (base_lines, target_lines)
    def __content_lines(self):
        # TODO: is this split sufficient?
        base_lines, target_lines = self.base_blob.content.split("\n"), self.target_blob.content.split("\n")

        # if base_lines[-1].strip() == '' and target_lines[-1].strip() == '':
        #     # remove end line of both blobs if it is blank (not sure if this is totally right)
        #     base_lines, target_lines = base_lines[:-1], target_lines[:-1]

        return (base_lines, target_lines)
    
    def fileCreated(self):
        return self.base_filepath is None and self.target_filepath is not None
    
    def fileDeleted(self):
        return self.base_filepath is not None and self.target_filepath is None
    
    def filepathChanged(self):
        return self.base_filepath != self.target_filepath
    
    def numInsertions(self):
        return self.trace.count(DiffTraceAction.ADD)
    
    def numDeletions(self):
        return self.trace.count(DiffTraceAction.DELETE)
    
    def numChanges(self):
        return self.numInsertions() + self.numDeletions()
    
    def getBaseBlob(self):
        return self.base_blob
    
    def getTargetBlob(self):
        return self.target_blob
    
    def getBaseFilepath(self):
        return self.base_filepath

    def getTargetFilepath(self):
        return self.target_filepath

    def print(self):
        print(f"diff --git a/{self.base_filepath} b/{self.target_filepath}")
        # TODO: add mode to this:
        print(f"index {utils.shortened_hash(self.base_blob.sha1)}..{utils.shortened_hash(self.target_blob.sha1)}")
        print(f"--- a/{self.base_filepath}")
        print(f"+++ b/{self.target_filepath}")
        (base_lines, target_lines) = self.__content_lines()
        print(f"{utils.bcolors.OKCYAN}@@ -1,{len(base_lines)} +1,{len(target_lines)} @@{utils.bcolors.ENDC}")

        blob1_idx, blob2_idx = 0, 0
        Log.Debug(self.trace)
        for t in self.trace:
            if t == DiffTraceAction.DELETE:
                print(f"{utils.bcolors.FAIL}-{base_lines[blob1_idx]}{utils.bcolors.ENDC}")
                blob1_idx += 1
            elif t == DiffTraceAction.ADD:
                print(f"{utils.bcolors.OKGREEN}+{target_lines[blob2_idx]}{utils.bcolors.ENDC}")
                blob2_idx += 1
            elif t == DiffTraceAction.MATCH:
                print(f" {base_lines[blob1_idx]}")
                blob1_idx, blob2_idx = blob1_idx + 1, blob2_idx + 1

    @staticmethod
    def MyersDiff(base, target):
        n, m = len(base), len(target)
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
                while x < n and y < m and base[x] == target[y]:
                    Log.Debug(f"incrementing x and y")
                    x, y = x+1, y+1

                Log.Debug(f"assigning v[{k}] = {x}")
                v[k] = x

                found = x >= n and y >= m
                if found: break
            
            V.append(v.copy())
            if found:
                Log.Debug(f"found d: {d}")
                return FileDiff.MyersDiffGetPath(base, target, V)
        # theoretically not possible:
        return None

    @staticmethod
    def MyersDiffGetPath(base, target, V):
        x, y = len(base), len(target)
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
                trace.append(DiffTraceAction.MATCH)
            elif dx > dy:
                trace.append(DiffTraceAction.DELETE)
            else:
                trace.append(DiffTraceAction.ADD)

        return trace
        

class CommitDiff:
    def __init__(self, base_tree, target_tree):
        self.file_diffs = []

        tree1_files, tree2_files = base_tree.getFiles(), target_tree.getFiles()
        all_filepaths = set(tree1_files.keys()).union(set(tree2_files.keys()))
        for filepath in all_filepaths:
            blob1, blob2 = tree1_files.get(filepath, None), tree2_files.get(filepath, None)

            if blob1 is None or blob2 is None:
                # TODO: remove this block once everything is clean
                continue

            if blob1.sha1 != blob2.sha1:
                diff = FileDiff(blob1, filepath, blob2, filepath)
                self.file_diffs.append(diff)

    def getFileDiffs(self):
        return sorted(self.file_diffs, key=lambda dff: dff.base_filepath)
    
    def getFileDiff(self, filepath):
        # TODO: this doesn't explicitly handle renames
        for dff in self.getFileDiffs():
            if dff.base_filepath == filepath:
                return dff
        return None

    def print(self):
        for file_diff in self.getFileDiffs():
            file_diff.print()

    def printNumericalSummary(self):
        num_insertions = 0
        num_deletions = 0
        for dff in self.getFileDiffs():
            num_insertions += dff.numInsertions()
            num_deletions += dff.numDeletions()

        summary_parts = [f"{len(self.getFileDiffs())} files changed"]
        if num_insertions > 0:
            summary_parts.append(f"{num_insertions} insertions(+)")
        if num_deletions > 0:
            summary_parts.append(f"{num_deletions} deletions(-)")
        print(f" {', '.join(summary_parts)}")
        

    def printVisualSummary(self):
        changes_to_print = {}
        num_insertions = 0
        num_deletions = 0
        for dff in self.getFileDiffs():
            if not dff.filepathChanged():
                insertions_str = f"{utils.bcolors.OKGREEN}{'+' * dff.numInsertions()}{utils.bcolors.ENDC}"
                deletions_str = f"{utils.bcolors.FAIL}{'-' * dff.numDeletions()}{utils.bcolors.ENDC}"
                changes_to_print[dff.base_filepath] = f"{dff.numChanges()} {insertions_str}{deletions_str}"
                num_insertions += dff.numInsertions()
                num_deletions += dff.numDeletions()

        # print the changes overview for each file
        rhs_length = sorted(map(lambda fp : len(fp), changes_to_print.keys()))[-1]
        for filepath, change in sorted(changes_to_print.items()):
            print(f" {filepath}{' ' * (rhs_length - len(filepath))} | {change}")
    
    def printExistenceChanges(self):
        for dff in self.getFileDiffs():
            if dff.fileCreated():
                print(f"create mode {dff.getTargetBlob().mode} {dff.getTargetFilepath()}")
            elif dff.fileDeleted():
                print(f"delete mode {dff.getBaseBlob().mode} {dff.getBaseFilepath()}")
