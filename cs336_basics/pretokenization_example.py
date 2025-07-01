import os
# 从typing模块导入BinaryIO类型
# BinaryIO是一个类型提示,用于表示二进制文件对象(如open()以'rb'模式打开的文件)
# 这个类型提示帮助IDE和类型检查器理解代码中的二进制文件操作
from typing import BinaryIO

def find_chunk_boundaries(
    file: BinaryIO, 
    desired_num_chunks: int,  # int是Python内置类型,不需要从typing导入
    split_special_token: bytes  # bytes也是Python内置类型,不需要从typing导入
) -> list[int]:
    """
    Chunk the file into parts that can be counted independently.
    May return fewer chunks if the boundaries end up overlapping.
    """
    # isinstance() 是 Python 内置函数,用于检查对象是否是指定类型的实例
    # 第一个参数是要检查的对象,第二个参数是类型
    # 如果对象是该类型的实例,返回 True,否则返回 False
    # 这里检查 split_special_token 是否为 bytes 类型
    assert isinstance(split_special_token, bytes), (
        "Must represent special token as a bytestring"
    )

    # Get total file size in bytes
    # file.seek(offset, whence) 用于移动文件指针位置
    # offset: 偏移量,表示要移动的字节数
    # whence: 移动的参考位置,可以是:
    #   - os.SEEK_SET (0): 从文件开头算起(默认)
    #   - os.SEEK_CUR (1): 从当前位置算起  
    #   - os.SEEK_END (2): 从文件末尾算起
    # 例如:
    # file.seek(0, os.SEEK_END) 移动到文件末尾 - 这里偏移量为0是因为我们想要移动到文件的末尾位置,
    # 而不需要任何额外的偏移。os.SEEK_END表示从文件末尾开始计算,偏移量0表示就停在末尾位置。
    # 如果偏移量是正数会超出文件末尾,如果是负数则会从末尾往前移动。
    # file.seek(0) 等同于 file.seek(0, os.SEEK_SET),移动到文件开头
    file.seek(0, os.SEEK_END)
    # tell()返回当前文件指针的位置,即文件的总大小(字节数)
    file_size = file.tell()
    # 将文件指针重新移动到文件开头,以便后续操作
    file.seek(0)

    chunk_size = file_size // desired_num_chunks

    # 初始化均匀分布的块边界位置
    # 这个注释说明了块的边界划分方式:
    # 每个块的范围是从当前索引开始,到下一个索引结束(不包含下一个索引)
    # 例如对于索引[0,100,200],第一个块是[0,100),第二个块是[100,200)
    chunk_boundaries = [i * chunk_size for i in range(desired_num_chunks + 1)]
    chunk_boundaries[-1] = file_size

    # 设置mini chunk的原因:
    # 1. 内存效率:不需要一次性读取整个文件,而是分批读取小块数据
    # 2. 性能优化:4KB是文件系统常用的页面大小,与操作系统的IO缓冲区大小匹配
    # 3. 实用性:在查找分隔符时,无需加载过大的数据块,可以逐步搜索
    mini_chunk_size = 4096  # 每次读取4KB数据

    # 从1开始是因为:
    # 1. 第0个边界(chunk_boundaries[0])总是0,即文件开头,不需要调整
    # 2. 最后一个边界(chunk_boundaries[-1])总是file_size,即文件结尾,也不需要调整
    # 3. 我们只需要调整中间的边界位置,使其对齐到特殊分隔符的位置
    for bi in range(1, len(chunk_boundaries) - 1):
        initial_position = chunk_boundaries[bi]
        file.seek(initial_position)  # Start at boundary guess
        while True:
            mini_chunk = file.read(mini_chunk_size)  # Read a mini chunk

            # 如果读取到文件末尾(EOF),说明这个边界应该在文件结尾
            # mini_chunk为空字节串b""表示已经到达文件末尾
            # 这种情况可能发生在:
            # 1. 当前边界位置已经非常接近文件末尾
            # 2. 在最后一小块数据中没有找到分隔符
            # 3. 继续读取导致到达了文件末尾
            # 虽然for循环不会遍历到最后一个边界(file_size),
            # 但在寻找中间边界时可能会读取到文件末尾
            if mini_chunk == b"":
                chunk_boundaries[bi] = file_size  # 将当前边界设置为文件大小
                break  # 跳出循环,继续处理下一个边界

            # 在mini chunk中查找特殊分隔符
            # found_at表示分隔符在当前mini chunk中的相对偏移位置
            found_at = mini_chunk.find(split_special_token)
            # find()方法在找不到目标字符串时返回-1
            # 当found_at != -1时,表示在mini_chunk中找到了split_special_token
            if found_at != -1:
                chunk_boundaries[bi] = initial_position + found_at
                break
            initial_position += mini_chunk_size

    # 对chunk_boundaries进行去重和排序的原因:
    # 1. 去重(set): 在寻找分隔符时,可能会出现多个边界被调整到同一个位置
    #    例如,如果连续的几个特殊分隔符出现在相近位置,相邻的边界可能会被调整到同一个分隔符处
    # 2. 排序(sorted): 由于边界的调整可能会改变原有的顺序
    #    为了确保边界是按照文件位置从小到大排列,需要重新排序
    # 注意: 去重可能导致实际的chunks数量少于desired_num_chunks
    # 原因:
    # 1. 如果多个原始边界被调整到同一个分隔符位置,去重会移除重复的边界
    # 2. 这种情况在分隔符分布不均匀时更容易发生
    # 3. 例如,如果文件中某些区域分隔符密集,而其他区域分隔符稀疏
    #    多个边界可能会被调整到同一个分隔符处,导致去重后chunks数量减少
    return sorted(set(chunk_boundaries))

## Usage
with open("your_file_path.txt", "rb") as f:
    # 每个块之后可以分配给一个进程并行处理
    # 例如num_processes=4时,文件会被分成4块,可以用4个进程同时处理
    boundaries = find_chunk_boundaries(
        f, num_processes, "<|endoftext|>".encode("utf-8"))
        
    # The following is a serial implementation, but you can parallelize this 
    # by sending each start/end pair to a set of processes.
    for start, end in zip(boundaries[:-1], boundaries[1:]):
        f.seek(start)
        # 设置errors="ignore"的原因:
        # 1. 在处理大文本文件时,可能会遇到无效的UTF-8字节序列
        # 2. 这些无效序列可能来自文件损坏、编码混合或非文本数据
        # 3. 使用ignore可以跳过这些无效字符,而不是抛出UnicodeDecodeError异常
        # 4. 虽然会丢失一些数据,但可以保证程序继续运行
        # 5. 对于预训练任务来说,丢失少量无效字符的影响通常可以接受
        # 读取边界问题说明:
        # 1. f.read(end - start)会精确读取从start到end之间的字节
        # 2. start边界是上一个分隔符的位置(包含分隔符)
        # 3. end边界是下一个分隔符的位置(不包含分隔符)
        # 4. 这样可以确保:
        #    - 每个chunk都包含完整的分隔符
        #    - 相邻chunk之间不会重复或遗漏内容
        #    - 分隔符可以作为chunk的边界标记
        # 读取字节范围说明:
        # 1. f.read(end - start)会读取从当前位置开始的(end - start)个字节
        # 2. 例如start=0, end=3时:
        #    - 会读取3个字节(0,1,2)
        #    - 不会读取位置3的字节
        # 3. 这符合Python的切片规则:[start:end]包含start但不包含end
        chunk = f.read(end - start).decode("utf-8", errors="ignore")
        # Run pre-tokenization on your chunk and store the counts for each pre-token