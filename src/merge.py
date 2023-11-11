from argparser import GitArgParser
from commit import Commit
from index import Index, IndexEntry
from diff import DiffTraceAction
from log import Log
from gitpath import GitPath

class ThreeWayMerge:
    def __init__(self, merge_base_hash, merge_source_rev, merge_source_hash, merge_target_hash):
        self.merge_base_hash = merge_base_hash
        self.merge_source_rev = merge_source_rev
        self.merge_source_hash = merge_source_hash
        self.merge_target_hash = merge_target_hash

        # get the diff of the current branch against the merge base
        self.target_diff = GitArgParser.Execute(f"diff {self.merge_base_hash} {self.merge_target_hash}", prnt=False)
        # get the diff of the source commit against the merge base
        self.source_diff = GitArgParser.Execute(f"diff {self.merge_base_hash} {self.merge_source_hash}", prnt=False)

        self.default_merge_commit_msg = f"Merge branch '{self.merge_source_rev}'"

    # for debugging
    def _printDiffs(self):
        print("TARGET: ")
        self.target_diff.print()
        print("\n\n\n")

        print("SOURCE: ")
        self.source_diff.print()

    def _updateIndexForConflict(self, index, conflict):
        # TODO: won't work for renames, deletions, etc
        filepath = conflict.getFilepath()

        merge_base_entry = IndexEntry.FromFile(filepath, conflict.getBaseFileHash())
        merge_base_entry.setStageInt(1)
        index.addEntry(merge_base_entry, key="hash")
        
        source_entry = IndexEntry.FromFile(filepath, conflict.getSourceFileHash())
        source_entry.setStageInt(3)
        index.addEntry(source_entry, key="hash")

        target_entry = index.getEntryWithHash(conflict.getTargetFileHash())
        target_entry.setStageInt(2)
        index.addEntry(target_entry, key="hash")

        index.writeToFile()

    def _finishMerge(self, conflicts):
        # write to MERGE_HEAD, MERGE_MSG, MERGE_MODE, ORIG_HEAD
        with open(GitPath.Path(GitPath.MERGE_HEAD), "w") as f:
            f.write(self.merge_source_hash)

        with open(GitPath.Path(GitPath.ORIG_HEAD), "w") as f:
            f.write(self.merge_target_hash)

        with open(GitPath.Path(GitPath.MERGE_MODE), "w") as f:
            f.write("")

        with open(GitPath.Path(GitPath.MERGE_MSG), "w") as f:
            f.write(self.default_merge_commit_msg) #TODO doesn't need to be a branch
            f.write("\n\n")
            f.write("# Conflicts:\n")
            for conflict in conflicts:
                f.write(f"#	{conflict.getFilepath()}\n")

        if len(conflicts) > 0:
            print("Automatic merge failed; fix conflicts and then commit the result.")
        else:
            GitArgParser.Execute(f"commit")

    def merge(self):
        # combine the file diffs into a list of tuples of the form (target_commit_file_diff, source_commit_file_diff)
        # for each file. Either diff can be None
        # TODO: this does not handle renames
        filepaths_target_commit = set([dff.base_filepath for dff in self.target_diff.getFileDiffs()])
        filepaths_source_commit = set([dff.base_filepath for dff in self.source_diff.getFileDiffs()])
        all_filepaths = filepaths_target_commit.union(filepaths_source_commit)
        combined_file_diffs = [
            (self.target_diff.getFileDiff(fp), self.source_diff.getFileDiff(fp)) 
            for fp in all_filepaths
        ]

        merge_base_files = Commit.FromHash(self.merge_base_hash).getTree().getFiles()
        source_files = Commit.FromHash(self.merge_source_hash).getTree().getFiles()
        target_files = Commit.FromHash(self.merge_target_hash).getTree().getFiles()

        # TODO: can probably get this info from the index after the merging?
        merge_has_conflicts = False
        # merge each file
        for (target_file_diff, source_file_diff) in combined_file_diffs:
            # TODO: this does not handle renames
            filepath = target_file_diff.base_filepath if target_file_diff else source_file_diff.base_filepath
            if target_file_diff is None:
                with open(filepath, "w") as f:
                    f.write(source_files[filepath].content)
                GitArgParser.Execute(f"add {filepath}")
            elif source_file_diff is None:
                with open(filepath, "w") as f:
                    f.write(target_files[filepath].content)
                GitArgParser.Execute(f"add {filepath}")
            else:
                # both commits have changed the file, need to reconcile

                # first, get the content of the merge base version
                if filepath not in merge_base_files:
                    print(f"something is wrong, merge base does not contain the file {filepath}")
                    exit(1) # TODO: throw error?

                # get the content of each file being merged
                base_file_content = merge_base_files[filepath].content
                source_file_content = source_files[filepath].content
                target_file_content = target_files[filepath].content

                # get the sha1 of each file being merged
                from commands import hash_object
                base_file_hash = hash_object(GitArgParser.Parse(f"hash-object"), prnt=False, content_override=base_file_content)
                source_file_hash = hash_object(GitArgParser.Parse(f"hash-object"), prnt=False, content_override=source_file_content)
                target_file_hash = hash_object(GitArgParser.Parse(f"hash-object"), prnt=False, content_override=target_file_content)

                # get the lines for each file being merged
                base_file_lines = base_file_content.split("\n")
                source_file_lines = source_file_content.split("\n")
                target_file_lines = target_file_content.split("\n")
                
                # go through both file diff traces line by line
                target_trace_counter = 0
                source_trace_counter = 0
                base_lineno = 0
                target_lineno = 0
                source_lineno = 0
                target_trace = target_file_diff.trace
                source_trace = source_file_diff.trace

                conflict = None
                conflicts = []
                while True:
                    target_trace_item = target_trace[target_trace_counter] if target_trace_counter < len(target_trace) else None
                    source_trace_item = source_trace[source_trace_counter] if source_trace_counter < len(source_trace) else None

                    target_line = target_file_lines[target_lineno]
                    source_line = source_file_lines[source_lineno]
                    Log.Debug(f"line: {base_file_lines[base_lineno]}, curr: {target_trace_item}, src: {source_trace_item}")

                    in_conflict = False

                    if target_trace_item == DiffTraceAction.MATCH and source_trace_item == DiffTraceAction.MATCH:
                        base_lineno += 1
                        target_trace_counter += 1
                        source_trace_counter += 1
                    elif target_trace_item == DiffTraceAction.MATCH and source_trace_item == DiffTraceAction.DELETE:
                        # delete the line
                        Log.Debug(f"\tDELETE: {base_file_lines[base_lineno]}")
                        base_file_lines.pop(base_lineno)
                        target_trace_counter += 1
                        source_trace_counter += 1
                    elif target_trace_item == DiffTraceAction.MATCH and source_trace_item == DiffTraceAction.ADD:
                        # add the line from source
                        Log.Debug(f"\tADD: {source_line}")
                        base_file_lines.insert(base_lineno, source_line)
                        base_lineno += 1 # inc by 2 to skip the line that was just added
                        source_trace_counter += 1 # Don't increment target_trace item because we need it for the next line

                        target_lineno -= 1
                    elif target_trace_item == DiffTraceAction.DELETE and source_trace_item == DiffTraceAction.DELETE:
                        Log.Debug(f"\tDELETE: {base_file_lines[base_lineno]}")
                        base_file_lines.pop(base_lineno)
                        target_trace_counter += 1
                        source_trace_counter += 1
                    elif target_trace_item == DiffTraceAction.ADD and source_trace_item == DiffTraceAction.ADD:
                        # TODO: this assumes conflicts are all the same length, need more heuristics
                        if target_file_lines[target_lineno] == source_file_lines[source_lineno]:
                            Log.Debug(f"\tMUTUAL_ADD: {target_line}")
                            base_file_lines.insert(base_lineno, target_line)
                            base_lineno += 1
                        else:
                            Log.Debug(f"\tCONFLICT: {target_line}, {source_line}")
                            # base_file_lines.insert(base_lineno, "CONFLICT: " + target_line + ", " + source_line)
                            if conflict is None:
                                # base_blob_hash = 
                                conflict = MergeConflict(filepath,
                                                         base_file_hash,
                                                         source_file_hash,
                                                         target_file_hash,
                                                         base_lineno - 1, 
                                                         self.merge_source_rev, 
                                                         "HEAD") # TODO: always head??
                            conflict.addSourceLine(source_line)
                            conflict.addTargetLine(target_line)
                            in_conflict = True
                        target_trace_counter += 1
                        source_trace_counter += 1
                        # base_lineno += 1
                    else:
                        break

                    if not in_conflict and conflict is not None:
                        # We had a MergeConflict, but the conflict area ended
                        conflicts.append(conflict)
                        conflict = None

                    if target_trace_item is not None and target_trace_item != DiffTraceAction.DELETE:
                        target_lineno += 1
                    if source_trace_item is not None and source_trace_item != DiffTraceAction.DELETE:
                        source_lineno += 1
                    

                index = Index.FromFile()
                # insert all conflicts
                for conflict in conflicts:
                    conflict_lines = conflict.getAllLines()
                    conflict_start = conflict.getStartLineno()
                    for i in range(len(conflict_lines)):
                        base_file_lines.insert(conflict_start + i, conflict_lines[i])

                    self._updateIndexForConflict(index, conflict)

                # TODO: make this work for renames, deletions, etc
                with open(filepath, "w") as f:
                    content = "\n".join(base_file_lines)
                    f.write(content)

                print(f"Auto-merging {filepath}")
                if len(conflicts) > 0:
                    merge_has_conflicts = True
                    print(f"CONFLICT (content): Merge conflict in {filepath}")
                else:
                    with open(filepath, "w") as f:
                        f.write("\n".join(base_file_lines))
                    GitArgParser.Execute(f"add {filepath}")

        # TODO: rn, this fn expects conflicts to be unique per file, fix and update this
        self._finishMerge(conflicts)

class SimpleThreeWayMerge(ThreeWayMerge):
    def __init__(self, merge_base_hash, merge_source_rev, merge_source_hash, merge_target_hash):
        super().__init__(merge_base_hash, merge_source_rev, merge_source_hash, merge_target_hash)

    def merge(self):
        # combine the file diffs into a list of tuples of the form (target_commit_file_diff, source_commit_file_diff)
        # for each file. Either diff can be None
        # TODO: this does not handle renames
        filepaths_target_commit = set([dff.base_filepath for dff in self.target_diff.getFileDiffs()])
        filepaths_source_commit = set([dff.base_filepath for dff in self.source_diff.getFileDiffs()])
        all_filepaths = filepaths_target_commit.union(filepaths_source_commit)
        combined_file_diffs = [
            (self.target_diff.getFileDiff(fp), self.source_diff.getFileDiff(fp)) 
            for fp in all_filepaths
        ]

        merge_base_files = Commit.FromHash(self.merge_base_hash).getTree().getFiles()
        source_files = Commit.FromHash(self.merge_source_hash).getTree().getFiles()
        target_files = Commit.FromHash(self.merge_target_hash).getTree().getFiles()

        index = Index.FromFile()

        conflicts = []
        # merge each file
        for (target_file_diff, source_file_diff) in combined_file_diffs:
            # TODO: this does not handle renames
            filepath = target_file_diff.base_filepath if target_file_diff else source_file_diff.base_filepath
            print(f"Auto-merging {filepath}")
            if target_file_diff is None:
                with open(filepath, "w") as f:
                    f.write(source_files[filepath].content)
                GitArgParser.Execute(f"add {filepath}")
            elif source_file_diff is None:
                with open(filepath, "w") as f:
                    f.write(target_files[filepath].content)
                GitArgParser.Execute(f"add {filepath}")
            else:
                # get the content of each file being merged
                base_file_content = merge_base_files[filepath].content
                source_file_content = source_files[filepath].content
                target_file_content = target_files[filepath].content

                source_file_lines = source_file_content.split("\n")
                target_file_lines = target_file_content.split("\n")

                # get the sha1 of each file being merged
                from commands import hash_object
                base_file_hash = hash_object(GitArgParser.Parse(f"hash-object"), prnt=False, content_override=base_file_content)
                source_file_hash = hash_object(GitArgParser.Parse(f"hash-object"), prnt=False, content_override=source_file_content)
                target_file_hash = hash_object(GitArgParser.Parse(f"hash-object"), prnt=False, content_override=target_file_content)
                # both commits have changed the file, create a conflict
                conflict = MergeConflict(filepath, base_file_hash, source_file_hash, target_file_hash, 0, self.merge_source_rev, "HEAD")
                for line in source_file_lines:
                    conflict.addSourceLine(line)
                for line in target_file_lines:
                    conflict.addTargetLine(line)

                conflict_lines = conflict.getAllLines()
                with open(filepath, "w") as f:
                    f.write("\n".join(conflict_lines))

                self._updateIndexForConflict(index, conflict)
                conflicts.append(conflict)

                print(f"CONFLICT (content): Merge conflict in {filepath}")

        self._finishMerge(conflicts)

class MergeConflict:
    def __init__(self, filepath, base_file_hash, source_file_hash, target_file_hash, start_lineno, source_label, target_label):
        self.filepath = filepath # TODO: doesn't work for renames
        self.base_file_hash = base_file_hash
        self.source_file_hash = source_file_hash
        self.target_file_hash = target_file_hash
        self.start_lineno = start_lineno
        self.source_label = source_label
        self.target_label = target_label
        self.source_lines = []
        self.target_lines = []

    def addTargetLine(self, line):
        self.target_lines.append(line)

    def addSourceLine(self, line):
        self.source_lines.append(line)

    def getStartLineno(self):
        return self.start_lineno

    def getAllLines(self):
        if len(self.target_lines) + len(self.source_lines) == 0:
            return []

        all_lines = []
        all_lines.append(f"<<<<<<< {self.target_label}")
        for line in self.target_lines:
            all_lines.append(line)
        all_lines.append("=======")
        for line in self.source_lines:
            all_lines.append(line)
        all_lines.append(f">>>>>>> {self.source_label}")
        return all_lines
    
    def getBaseFileHash(self):
        return self.base_file_hash
    
    def getSourceFileHash(self):
        return self.source_file_hash
    
    def getTargetFileHash(self):
        return self.target_file_hash
    
    def getFilepath(self):
        return self.filepath