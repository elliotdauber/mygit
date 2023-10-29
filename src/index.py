import struct
import os
import utils
import binascii
from log import Log
from tree import Tree, Blob
from gitpath import GitPath

class IndexHeader:
    def __init__(self, num_entries, sig=b"DIRC", version=2):
        self.sig = sig
        self.version = version
        self.num_entries = num_entries

    def print(self):
        print("[header]")
        print(f"\tsignature: {self.sig.decode('utf-8')}")
        print(f"\tversion: {self.version}")
        print(f"\tentries: {self.num_entries}")

class IndexEntry:
    def __init__(self, sha1, ctime, mtime, mode, dev, ino, uid, gid, flags, filesize, filename):
        self.sha1 = sha1
        self.ctime = ctime
        self.mtime = mtime
        self.mode = mode
        self.dev = dev
        self.obj_type = 0b1000 # normal file
        self.permission = 0o0755 # TODO
        self.ino = ino
        self.uid = uid
        self.gid = gid
        self.filesize = filesize
        self.flags = flags
        self.name_length = len(filename) if len(filename) < 0xFFF else 0xFFF
        self.filename = filename

    def toBinary(self):
        Log.Debug(
            f'''file: {self.filename}
            {int(self.ctime)},
            {int((self.ctime - int(self.ctime)) * 1000000000)},
            {int(self.mtime)},
            {int((self.mtime - int(self.mtime)) * 1000000000)},
            {self.dev},
            {self.ino},
            {self.mode},
            {self.uid},
            {self.gid},
            {self.filesize},
            {self.sha1},
            {self.flags}'''
        )

        data = struct.pack(
            Index.ENTRY_FORMAT_STRING,
            int(self.ctime),
            int((self.ctime - int(self.ctime)) * 1000000000),
            int(self.mtime),
            int((self.mtime - int(self.mtime)) * 1000000000),
            self.dev,
            self.ino,
            self.mode,
            self.uid,
            self.gid,
            self.filesize,
            self.sha1,
            self.flags
        )

        data += self.filename
        padding_length = (8 - (len(data) % 8)) or 8
        data += b'\x00' * padding_length
        return data
        

    def print(self, entryno):
        print("[entry]")
        print(f"\tentry: {entryno}")
        print(f"\tctime: {self.ctime}")
        print(f"\tmtime: {self.mtime}")
        print(f"\tdev: {self.dev}")
        print(f"\tino: {self.ino}")
        print(f"\tmode: {self.getModeStr()}")
        print(f"\tuid: {self.uid}")
        print(f"\tgid: {self.gid}")
        print(f"\tsize: {self.filesize}")
        print(f"\tsha1: {self.getSha1Str()}")
        print(f"\tflags: {self.flags}")
        print(f"\tassume-valid: {self.getFlag(0b10000000)}")
        print(f"\textended: {self.getFlag(0b01000000)}")
        print(f"\tstage: {self.getStageInt()} {self.getStage()}")
        print(f"\tname: {self.getFilepathStr()}")

    #TODO: redo the way flags are handled, make api nicer
    def getFlag(self, mask):
        return bool(self.flags & (mask << 8))
    
    def setFlag(self, mask, val):
        if val:
            self.flags |= (mask << 8)
        else:
            self.flags &= ~(mask << 8)
    
    def getStage(self):
        return (self.getFlag(0b00100000), self.getFlag(0b00010000))
    
    def getStageInt(self):
        stage = self.getStage()
        return (stage[0] << 1) + stage[1]
    
    def setStageInt(self, stage):
        if stage > 3:
            return
        self.setFlag(0b00100000, stage > 1)
        self.setFlag(0b00010000, stage % 2 == 1)
    
    def getMTime(self):
        return self.mtime
    
    def getModeStr(self):
        return '%06o' % self.mode
    
    def getCTime(self):
        return self.ctime
    
    def getFilepathStr(self):
        return self.filename.decode('utf-8')
    
    def getSha1Str(self):
        return binascii.hexlify(self.sha1).decode('ascii')
    
    def sortPred(self):
        stage = self.getStage()
        return f"{self.getFilepathStr()}{self.getStageInt()}"

    @staticmethod
    def FromFile(filepath, sha1):
        stat = os.stat(filepath)
        # Log.Debug(stat)
        return IndexEntry(
            binascii.unhexlify(sha1),
            stat.st_ctime,
            stat.st_mtime,
            stat.st_mode,
            stat.st_dev,
            stat.st_ino,
            stat.st_uid,
            stat.st_gid,
            len(filepath), # TODO: this should also include the flags
            stat.st_size,
            filepath.encode('utf-8')
        )

class Index:
    HEADER_FORMAT_STRING = '!4sII'
    ENTRY_FORMAT_STRING = "!IIIIIIIIII20sH" # This doesn't include filename or padding (these must be calculated later)

    # https://git-scm.com/docs/index-format

    def __init__(self, header, entries):
        self.header = header
        self.entries = entries
        self.sortEntries()
    
    def writeToFile(self, filepath=GitPath.Path(GitPath.index)):
        with open(filepath, "wb") as f:
            contents_before_checksum = b""

            header = struct.pack(Index.HEADER_FORMAT_STRING, b'DIRC', self.header.version, self.header.num_entries)
            contents_before_checksum += header
            f.write(header)

            for entry in self.entries:
                entry_contents = entry.toBinary()
                contents_before_checksum += entry_contents
                f.write(entry_contents)

            #TODO: write extensions
            Log.Debug(contents_before_checksum)

            # TODO: figure out how to do this correctly
            checksum = utils.sha1hash_bytes(contents_before_checksum)
            f.write(checksum)

            Log.Debug(f"wrote index file at {filepath} with checksum {binascii.hexlify(checksum)}")

    def print(self):
        self.header.print()
        for i in range(len(self.entries)):
            self.entries[i].print(i+1)
        # print("[checksum]")
        # print("\tchecksum: True")
        # print(f"\tsha1: {binascii.hexlify(self.checksum).decode('ascii')}")

    def addEntry(self, entry, key="filepath"):
        # TODO: need this?
        # if self.containsEntryWithHash(entry.getSha1Str()):
        #     return
        
        # Remove any existing entry for the same file
        if key == "filepath":
            self.removeEntryWithFilepath(entry.getFilepathStr())
        elif key == "hash":
            self.removeEntryWithHash(entry.getSha1Str())
        else:
            return

        self.entries.append(entry)
        self.header.num_entries += 1
        self.sortEntries()

    def sortEntries(self):
        self.entries.sort(key=lambda entry : entry.sortPred())

    def containsEntryWithHash(self, sha1):
        for entry in self.entries:
            if entry.getSha1Str() == sha1:
                return True
        return False
    
    def getEntryWithHash(self, sha1):
        for entry in self.entries:
            if entry.getSha1Str() == sha1:
                return entry
        return None
    
    def removeEntryWithHash(self, sha1):
        entry = self.getEntryWithHash(sha1)
        if entry is not None:
            self.entries.remove(entry)
            self.header.num_entries -= 1
    
    def containsEntryWithFilepath(self, filepath):
        for entry in self.entries:
            if entry.getFilepathStr() == filepath:
                return True
        return False
    
    def getEntryWithFilepath(self, filepath):
        for entry in self.entries:
            if entry.getFilepathStr() == filepath:
                return entry
        return None
    
    def removeEntryWithFilepath(self, filepath):
        entry = self.getEntryWithFilepath(filepath)
        if entry is not None:
            self.entries.remove(entry)
            self.header.num_entries -= 1



    # Takes some inspo from https://github.com/sbp/gin/blob/master/gin
    @staticmethod
    def FromFile(index_filepath=GitPath.Path(GitPath.index)):
        if not os.path.exists(index_filepath):
            Log.Debug(f"no index file exists at {index_filepath}, creating one")
            # Create a blank index file if none exists
            header = IndexHeader(0)
            newIndex = Index(header, [])
            newIndex.writeToFile(index_filepath)
            return newIndex
        

        index_file_size = os.path.getsize(index_filepath)
        header_size = struct.calcsize(Index.HEADER_FORMAT_STRING)

        if index_file_size < header_size:
            return None

        with open(index_filepath, "rb") as f:
            # Parse header
            header_contents = f.read(struct.calcsize(Index.HEADER_FORMAT_STRING))
            header_parts = struct.unpack(Index.HEADER_FORMAT_STRING, header_contents)
            signature, version, entry_count = header_parts
            header = IndexHeader(entry_count, signature, version)

            # Parse entries
            entries = []
            for i in range(entry_count):
                 # https://git-scm.com/docs/index-format
                entry_length_unpadded = struct.calcsize(Index.ENTRY_FORMAT_STRING)
                entry_contents = f.read(entry_length_unpadded)
                entry_parts = struct.unpack(Index.ENTRY_FORMAT_STRING, entry_contents)
                ctime, ctime_nano, mtime, mtime_nano, dev, ino, mode, uid, gid, file_size, sha1, flags = entry_parts
                ctime = float(ctime) + (ctime_nano / 1000000000)
                mtime = float(mtime) + (mtime_nano / 1000000000)

                filename_length = flags & 0xFFF
                filename = ""
                # TODO: for now we just assume the filename length is reasonably short (less than 0xFFF)
                ## This will break if it's not so come back later and fix
                if filename_length < 0xFFF:
                    filename = f.read(filename_length)
                    entry_length_unpadded += filename_length
                else:
                    print("Filename too long, unimplemented code path")
                    exit(1)
                    # TODO: handle extremely long filenames
                
                padding_length = (8 - (entry_length_unpadded % 8)) or 8
                padding = f.read(padding_length)
                for char in padding:
                    if char != 0:
                        print(f"Padding contained non-null chars ({padding}), aborting")
                        exit(1)

                entry = IndexEntry(
                    sha1,
                    ctime,
                    mtime,
                    mode,
                    dev,
                    ino,
                    uid,
                    gid,
                    flags,
                    file_size,
                    filename
                )
                entries.append(entry)

            # TODO: Parse extensions
            while f.tell() < index_file_size - 20:
                signature = f.read(4).decode('utf-8')

                size_contents = f.read(struct.calcsize("!I"))
                size = struct.unpack("!I", size_contents)[0]

                data = f.read(size)
                # TODO: incorporate this
                # Log.Debug(f"{signature}, {size}, {data}")

            # Parse checksum
            checksum = f.read(20)

            return Index(header, entries)
        
    @staticmethod
    def FromTree(tree):
        def getEntriesForTree(_tree):
            _entries = []
            for path, node in _tree.getNodesExpanded().items():
                if type(node) == Blob:
                    _entries.append(IndexEntry.FromFile(path, node.sha1))
                elif type(node) == Tree:
                    _entries.extend(getEntriesForTree(node))
            return _entries
        
        entries = getEntriesForTree(tree)
        header = IndexHeader(len(entries))
        return Index(header, entries)

                

