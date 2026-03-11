"""
Vector Database Creation Script
================================

This script creates ChromaDB vector databases from markdown files for the RAG system.

Process:
1. Loads markdown files from data_sources/Data/Context/
2. Iteratively splits documents into chunks (based on markdown headers)
3. Generates embeddings
4. Stores in ChromaDB vector database

Requirements:
- Ollama must be running
- Current embeddings model must be downloaded (set in `config/runtime.py`)
- Data files (markdown) must be present in data_sources/Data/Context/

Important: There are three hardcoded database options: teacher, study adviser, and all (general).
The system will ask which database to create when you run the script. 
If you add a new database type, update all three places: `select_database_type()`, `DB_CONFIG` in this script, and the path config in `config/paths.py`.
"""

from pathlib import Path
from typing import List, Dict, Tuple

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_chroma import Chroma

from config.runtime import CURRENT_EMBEDDINGS_MODEL
from config.paths import (
    CONTEXT_PATH,
    CHUNK_OVERVIEW_PATH_STUDY_ADVISER,
    CHROMA_DB_PATH_STUDY_ADVISER,
    CHUNK_OVERVIEW_PATH_TEACHER,
    CHROMA_DB_PATH_TEACHER,
    CHUNK_OVERVIEW_PATH_ALL,
    CHROMA_DB_PATH_ALL,
)
from config.tunables import MAX_CHARS, MIN_CHARS

# --- MAIN PROCESSING FUNCTION --- #
def main() -> None:
    """Main function to orchestrate database creation process."""
    global CURRENT_CHUNK_OVERVIEW_PATH, CURRENT_CHROMA_DB_PATH
       
    # Load markdown files
    print("\n[1/4] Loading markdown files...")
    documents = load_md_documents()
    if not documents:
        print(f"\n❌ No documents found in {CONTEXT_PATH}")
        return

    # Split into chunks
    print("\n[2/4] Splitting documents into chunks...")
    chunks = split_documents(documents)
    print(f"Split {len(documents)} documents into {len(chunks)} chunks")

    # Select database type (update selection, DB_CONFIG, and config/paths.py when adding a new database type)
    current_database = select_database_type()
    
    # Map selection to paths
    DB_CONFIG = {
        'all': (CHUNK_OVERVIEW_PATH_ALL, CHROMA_DB_PATH_ALL),
        'teacher': (CHUNK_OVERVIEW_PATH_TEACHER, CHROMA_DB_PATH_TEACHER),
        'adviser': (CHUNK_OVERVIEW_PATH_STUDY_ADVISER, CHROMA_DB_PATH_STUDY_ADVISER),
    }
    
    CURRENT_CHUNK_OVERVIEW_PATH, CURRENT_CHROMA_DB_PATH = DB_CONFIG[current_database]

    # Export chunk overview
    print("\n[3/4] Exporting chunk overview...")
    export_chunks_to_markdown_file(chunks, CURRENT_CHUNK_OVERVIEW_PATH)

    # Add folder context
    print("\n[4/4] Adding folder context...")
    chunks = add_folder_context_to_chunks(chunks)
    print(f"✓ Processed {len(chunks)} chunks")

    # Create database
    print(f"\nReady to create database at: {CURRENT_CHROMA_DB_PATH}")
    save_db = input("\nProceed? (y/n): ").strip().lower()
    
    if save_db in ['y', 'yes']:
        save_to_chroma(chunks)
        print_summary(documents, chunks, current_database)
    else:
        print("\nNo database created. Run script again to create database.\n")


# ============================================================================
# SUPPORTING FUNCTIONS
# ============================================================================

def select_database_type() -> str:
    """Interactive prompt to select which database to create."""

    print("\nSelect database: [all | teacher (t) | adviser (ad)] (default: all)")
    choice = input("> ").strip().lower()
    
    if choice in ['teacher', 't']:
        print("✓ Teacher database")
        return 'teacher'
    elif choice in ['adviser', 'advisor', 'ad']:
        print("✓ Study Adviser database")
        return 'adviser'
    else:
        print("✓ All databases")
        return 'all'


def print_summary(documents: List[Document], chunks: List[Document], db_type: str) -> None:
    """Print summary of the database creation process."""
    print("\n" + "="*70)
    print(f"✓ Database created: {db_type} | {len(documents)} docs → {len(chunks)} chunks")
    print("="*70 + "\n")


# --- File loading and processing --- #
def load_md_documents() -> List[Document]:
    """
    Load all markdown files from CONTEXT_PATH into Document objects.
    Folder context is retrieved and added to chunk metadata.

    Returns: a list of Document objects.
    """

    documents: List[Document] = []

    if not CONTEXT_PATH.exists():
        print(f"\n❌ Error: Context path does not exist: {CONTEXT_PATH}")
        print("\nPlease ensure markdown files are present in data_sources/Data/Context/")
        print("See README.md section 'Required Data Files' for setup instructions.")
        raise FileNotFoundError(f"The context path {CONTEXT_PATH} does not exist.")

    for path in CONTEXT_PATH.rglob("*.md"): # Only load .md (Markdown) files
        
        # Skip folder context files
        if path.name.endswith("-folder_context.md"):
            continue

        try:
            file_content = path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"Error reading {path}: {e}")
            continue

        metadata: Dict = {
            "file": path.name,
            "folder_context": "None",
            "split_tag": "To be added"
        }

        folder_context = get_folder_context(path)
        if folder_context is None:
            folder_context = "None"

        if folder_context:
            metadata["folder_context"] = folder_context
        
        documents.append(Document(page_content=file_content, metadata=metadata))
    
    print(f"✓ Loaded {len(documents)} files")
    return documents



def get_folder_context(file_path: Path) -> str:
    """
    Retrieve the folder context for a given file by searching for a '*-folder_context.md',
    moving up the directory hierarchy until one is found or until reaching `CONTEXT_PATH`.

    Folder context is meant to provide additional background information relevant to all files in that folder.

    Returns: the folder context string, or None if not found.
    """
    
    current_dir = file_path.parent

    while current_dir >= CONTEXT_PATH:
        # Look for any file matching *-folder_context.md in the current directory
        context_files = list(current_dir.glob('*-folder_context.md'))

        if context_files:
            try:
                folder_context = context_files[0].read_text(encoding="utf-8")
                return folder_context
            except IndexError:
                print(f"No folder context file found in {current_dir}")
                return None
        
        # Move up one directory level until a match is found or highest directory CONTEXT_PATH is reached
        if current_dir == CONTEXT_PATH:
            break
        current_dir = current_dir.parent
    
    return None



# --- Document splitting and chunking --- #
def split_documents(documents: List[Document]) -> List[Document]:
    """
    Split documents into chunks based on markdown headers.
    Size constraints (MIN_CHARS & MAX_CHARS, defined in `config/tunables.py`) are enforced.

    Returns: a list of Document chunks.
    """

    all_chunks: List[Document] = []
    for doc in documents:

        doc_content = doc.page_content
        if not doc_content:
            raise ValueError("Document content is empty.")
        
        metadata: Dict = doc.metadata
        if not metadata:
            raise ValueError("Document metadata is missing.")
        
        if len(doc_content) < MAX_CHARS:
            metadata["split_tag"] = "Original file smaller than MAX_CHARS, no split"
            all_chunks.append(doc)
            continue
        
        chunks = extract_chunks_from_doc(doc)
        all_chunks.extend(chunks)

    all_chunks = enforce_chunk_size_constraints(all_chunks)

    return all_chunks



def add_folder_context_to_chunks(chunks: List[Document]) -> List[Document]:
    """
    Retrieve folder context from metadata and add it to each chunk's content.
    
    Returns: a list of Document chunks including folder context.
    """
    new_chunks: List[Document] = []
    
    for chunk in chunks:
        folder_context = chunk.metadata.get('folder_context', 'None')
        
        # Only add if folder context exists and is not "None"
        if folder_context and folder_context != 'None':
            # Prepend folder context to the chunk content for embedding
            new_content = f"[FOLDER CONTEXT]\n{folder_context}\n\n[CHUNK CONTENT]\n{chunk.page_content}"
            chunk.page_content = new_content
        
        new_chunks.append(chunk)
    
    return new_chunks



def extract_chunks_from_doc(doc: Document) -> List[Document]:
    """
    Extract chunks from a single Document based on markdown headers.

    Returns a list of Document chunks.
    """

    doc_content = doc.page_content
    metadata: Dict = doc.metadata
    
    headers_to_split_on = [("##", "h2")] # First try splitting on H2 headers (as H1 headers are used for titles)

    try:
        chunks = split_content_by_headers(doc_content, metadata, headers_to_split_on)

        for chunk in chunks:
            chunk.metadata["split_tag"] = f"Split on {headers_to_split_on[0][0]} ({headers_to_split_on[0][1]})"
    
        # If split produced only one chunk (no headers found), return original document
        if len(chunks) == 1:
            return [doc]
        
        return chunks

    except Exception as e:
        print(f"Error splitting document {metadata.get('file', 'unknown')}: {e}")
        return []



def split_content_by_headers(content: str, metadata: Dict, headers_to_split_on: List[Tuple[str, str]]) -> List[Document]:
    """
    Split content based on specified markdown headers.

    Returns a list of Document chunks.
    """
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on, strip_headers=False)
    split_content = splitter.split_text(content)

    if not split_content:
        raise ValueError("Markdown splitting returned no chunks.")
    
    chunks: List[Document] = []

    for chunk in split_content:
        content = chunk.page_content
        chunk_metadata = metadata.copy()
        chunk_metadata["split_tag"] = f"Split on headers: {headers_to_split_on}"
        chunks.append(Document(page_content=content, metadata=chunk_metadata))

    return chunks



def split_oversized_chunk_iteratively(chunk: Document) -> List[Document]:
    """
    Iteratively split an oversized chunk using smaller markdown headers.

    Returns a list of resized Document chunks.
    """
    header_levels = [
        [("###", "h3")],
        [("####", "h4")],
        [("#####", "h5")]
    ]

    current_chunks = [chunk]

    for headers in header_levels:
        new_chunks: List[Document] = []
        any_oversized = False
        split_occurred = False
        
        for current_chunk in current_chunks:
            if len(current_chunk.page_content) > MAX_CHARS:
                any_oversized = True # Found at least one oversized chunk - splitting again
                try:
                    split_chunks = split_content_by_headers(
                        current_chunk.page_content,
                        current_chunk.metadata,
                        headers
                    )
                    # Check if splitting actually produced multiple chunks (i.e., headers were found)
                    if len(split_chunks) > 1:
                        split_occurred = True
                        new_chunks.extend(split_chunks)
                    else:
                        # No headers found at this level, keep chunk as is
                        new_chunks.append(current_chunk)
                except Exception as e:
                    print(f"Failed to split with {headers[0][0]}: {e}. Keeping chunk as is.")
                    new_chunks.append(current_chunk)
            else:
                new_chunks.append(current_chunk)
        
        current_chunks = new_chunks
        
        # If no split occurred and we still have oversized chunks, stop trying smaller headers
        if not split_occurred and any_oversized:
            for chunk_item in current_chunks:
                if len(chunk_item.page_content) > MAX_CHARS:
                    chunk_item.metadata["split_tag"] = chunk_item.metadata.get("split_tag", "") + ", no smaller headers available"
            break
        
        if not any_oversized:
            break
    
    return current_chunks



def can_merge_chunks(chunk1: Document, chunk2: Document) -> bool:
    """
    Determine if two chunks can be merged.
    
    Chunks can be merged if:
    - They originate from the same file
    - The merged size does not exceed MAX_CHARS
    
    Returns bool True if chunks can be merged, False otherwise.
    """
    # Next chunk is from another file
    if chunk1.metadata.get("file") != chunk2.metadata.get("file"):
        return False
    
    merged_size = len(chunk1.page_content) + len(chunk2.page_content)
    return merged_size <= MAX_CHARS



def merge_two_chunks(chunk1: Document, chunk2: Document) -> Document:
    """
    Merge two chunks together, combining their content and metadata.
    
    Returns one merged Document chunk.
    """
    merged_content = chunk1.page_content + "\n\n" + chunk2.page_content
    merged_metadata = chunk1.metadata.copy()
    merged_metadata["split_tag"] = merged_metadata["split_tag"] + ", merged"
    return Document(page_content=merged_content, metadata=merged_metadata)



def merge_undersized_chunks(chunks: List[Document]) -> List[Document]:
    """
    Merge undersized chunks with the next chunk from the same file,
    only if the merge does not result in a chunk exceeding MAX_CHARS.
    
    Returns a list of resized Document chunks.
    """
    merged_chunks: List[Document] = []
    i = 0

    while i < len(chunks):
        current_chunk = chunks[i]
        current_size = len(current_chunk.page_content)

        # If chunk is not undersized, add it to the list
        if current_size >= MIN_CHARS:
            merged_chunks.append(current_chunk)
            i += 1
            continue

        # First try forward merge 
        if i + 1 < len(chunks):
            next_chunk = chunks[i + 1]

            if can_merge_chunks(current_chunk, next_chunk):
                merged_chunk = merge_two_chunks(current_chunk, next_chunk)
                chunks[i + 1] = merged_chunk
                i += 1
                continue

        # Otherwise, try backward merge 
        if merged_chunks and merged_chunks[-1].metadata.get("file") == current_chunk.metadata.get("file"):
            previous_chunk = merged_chunks[-1]
            if can_merge_chunks(previous_chunk, current_chunk):
                merged_chunk = merge_two_chunks(previous_chunk, current_chunk)
                merged_chunks[-1] = merged_chunk
                i += 1
                continue

        # Could not merge, add undersized chunk as-is
        merged_chunks.append(current_chunk)
        i += 1
    
    return merged_chunks


def enforce_chunk_size_constraints(chunks: List[Document]) -> List[Document]:
    """
    Enforce chunk size constraints based on MIN_CHARS and MAX_CHARS.
    
    Process:
    1. Split oversized chunks
    2. Merge undersized chunks with next chunk from same file

    Returns a list of resized Document chunks.
    """
    resized_chunks: List[Document] = []

    # First pass: handle oversized chunks
    for chunk in chunks:
        chunk_size = len(chunk.page_content)

        # Case 1: Chunk is correctly sized or undersized, continue to next chunk
        if chunk_size <= MAX_CHARS:
            resized_chunks.append(chunk)
            continue

        # Case 2: Chunk is too big -> split iteratively
        if chunk_size > MAX_CHARS:
            split_chunks = split_oversized_chunk_iteratively(chunk)
            resized_chunks.extend(split_chunks)
            continue

    # Second pass: handle undersized chunks
    resized_chunks = merge_undersized_chunks(resized_chunks)

    return resized_chunks



# --- Exporting chunks for Review --- #
def export_chunks_to_markdown_file(chunks: List[Document], output_path: Path) -> None:
    """
    Export all chunks to a markdown file organized by file:
    - File summary with all chunk sizes
    - All chunks for that file with metadata and content
    """
    try:
        # Group chunks by file
        chunks_by_file: Dict[str, List[Document]] = {}
        for chunk in chunks:
            file_name = chunk.metadata.get('file', 'unknown')
            if file_name not in chunks_by_file:
                chunks_by_file[file_name] = []
            chunks_by_file[file_name].append(chunk)
        
        with open(output_path, "w", encoding="utf-8") as f:
            for file_name, file_chunks in chunks_by_file.items():
                chunk_sizes = [len(chunk.page_content) for chunk in file_chunks]
                f.write(f"# File: {file_name} | Chunk lengths: {chunk_sizes}\n\n")
                
                # Write all chunks for this file
                for chunk_num, chunk in enumerate(file_chunks, 1):
                    # Add chunk number to metadata for database storage
                    chunk.metadata['chunk_num'] = chunk_num
                    
                    f.write(f"## Chunk {chunk_num}\n\n")
                    f.write(f"**Folder_context:** {chunk.metadata['folder_context']}\n\n")
                    f.write(f"**Split Tag:** {chunk.metadata['split_tag']}\n\n")
                    f.write(f"**Chunk Length:** {len(chunk.page_content)} characters\n\n")
                    f.write(f"**Content:**\n\n")
                    f.write(chunk.page_content)
                    f.write("\n\n---\n\n")
                
                f.write("\n")
                
        print(f"✓ Overview saved: {output_path.name}")
    except Exception as e:
        print(f"❌ Export failed: {e}")



# --- Saving to Chroma Database --- #
def save_to_chroma(chunks: List[Document]) -> None:
    """
    Save chunks to Chroma database with embeddings.
    
    This process:
    1. Checks for existing database
    2. Generates embeddings using Ollama
    3. Stores vectors in ChromaDB
    """
    try:
        # Check if database already exists
        if CURRENT_CHROMA_DB_PATH.exists():
            print(f"\nDatabase already exists. Overwrite? (y/n): ", end="")
            if input().strip().lower() not in ['y', 'yes']:
                print("⏭️  Cancelled.\n")
                return
            import shutil
            shutil.rmtree(CURRENT_CHROMA_DB_PATH)
        
        # Create database
        print(f"\nGenerating embeddings for {len(chunks)} chunks...")
        
        chroma_db = Chroma(
            persist_directory=str(CURRENT_CHROMA_DB_PATH),
            embedding_function=CURRENT_EMBEDDINGS_MODEL
        )
        chroma_db.add_documents(chunks)

        print(f"✓ Saved to {CURRENT_CHROMA_DB_PATH.name}")
    except Exception as e:
        print(f"\n❌ Failed: {e}")
        raise



if __name__ == "__main__":
    main()