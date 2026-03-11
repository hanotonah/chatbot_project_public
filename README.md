# Creative Technology Virtual Assistant Platform

A multi-assistant platform designed to support university students through conversational Virtual Assistants (VAs). Built using Retrieval-Augmented Generation (RAG) with local language models via Ollama. The system includes a keyword-based handover system to switch between VAs during the conversation.

**Purpose:** Research tool for analyzing student-VA interactions 

**Author:** Hannah Ottenschot, HMI, University of Twente  

**Last updated:** March 2026 

---

## Table of Contents

1. [Overview](#overview)
2. [Setup Instructions](#setup-instructions)
3. [Configuration](#configuration)
4. [Populating the data_sources Folder](#populating-the-data_sources-folder)

---

### Overview

This platform enables conversations with specialized VAs, each with distinct roles specified through their persona, prompt, and database used (domain knowledge).

#### Conversation flow - single or multiple VAs

The system supports interaction with a single VA, as well as a VA handing over the conversation to another VA based on keyword detection. Each VA has access to its own vector database containing relevant knowledge. 

Which VAs are initialized at the start of the conversation depends on which VAs have been included in the current condition, defined in [config/conditions.py](config/conditions.py).

**In case of a single VA**, the following happens when a user sends a query:
1. The query is preprocessed by expanding abbreviations to improve RAG results (see [src/chat/preprocessing/](src/chat/preprocessing/))
2. The expanded query is used to retrieve relevant chunks from the database (see [src/rag/](src/rag/))
3. The VA generates a response based on retrieved context and conversation history (see [src/chatbot_core/chatbots/base_chatbot.py](src/chatbot_core/chatbots/base_chatbot.py))

**In case the current condition includes multiple VAs**, a handover can also be triggered:

4. If at least a certain amount of turns has passed and the (expanded) query contains one of the predetermined keywords (see [src/chat/query_router.py](src/chat/query_router.py)), the current VA does not answer the query, but triggers a handover
5. Current conversation history and user query are saved
6. The current VA notifies the user that the conversation will be handed over to another VA (see [src/app/flask_app.py](src/app/flask_app.py))
7. The chat switches to the new VA, which responds to the previous user query using conversation history
8. The conversation continues with the new VA


## Setup instructions

### Step 1: Install Ollama

Ollama runs LLMs locally on your computer.

1. Download & install Ollama from [https://ollama.ai](https://ollama.ai)
2. Open a terminal/command prompt
3. Download required models using the `ollama pull [model name]` command. See [https://ollama.com/search](https://ollama.com/search) for all available models.

Running `ollama list` shows you all the models you have currently downloaded.

### Step 2: Setup Python environment

1. Copy this GitHub repository to your local machine
2. Install the required packages (see [requirements.txt](requirements.txt)) in a `.venv`

Make sure you have a viable Python version installed. The system was tested using Python 3.13.5.

### Step 3: Setup data_sources folder

**Note:** Knowledge base files are not included in this repository.

- If you received data files separately, place them in `data_sources/Database/` following the structure shown in [File Structure](#file-structure).
- If using your own files, see [Populating the data_sources Folder](#populating-the-data_sources-folder) to generate vector databases.

### Step 4: Run the application

Before starting the application, make sure that the following is true:
1. Ollama is running (use `ollama serve` to check)
2. Virtual environment is activated
3. All data files are in place (see [Populating the data_sources Folder](#populating-the-data_sources-folder))

There are two options for starting the application:
- **Command Line Interface (CLI):** run with [run_cli.py](run_cli.py)
- **Flask web application:** run with [run_flask.py](run_flask.py)

---

## Configuration

Several aspects of the system can be tuned. Configuration of variables is centralized in the [config/](config/) directory.

### Model selection ([runtime.py](config/runtime.py))

Specify which Ollama models to use by changing the `CURRENT_*` variables. Any model available through Ollama can be used. Download alternatives with the command `ollama pull [model name]`.

### Retrieval parameters ([tunables.py](config/tunables.py))

Adjust system behavior:
- `CHUNKS_INCLUDED_IN_CONTEXT`: Number of relevant chunks to retrieve
- `RELEVANCE_THRESHOLD`: Similarity cutoff for retrieval. Lower scores mean higher relevance
- `MIN_TURNS_BEFORE_HANDOVER`: Minimum conversation turns before handover can take place. Ensures that the user has had at least some interaction with each VA.
- `ENABLE_RESPONSE_SUMMARIZATION`: Enable/disable automatic response summarization (default: disabled)
- `RESPONSE_SENTENCE_LIMIT`: Sentence threshold used if summarization is enabled
- `MAX_CHARS` / `MIN_CHARS`: Target chunk sizes for database creation

### Study conditions ([conditions.py](config/conditions.py))

Define condition specifying:
- Which VAs are available within an interaction
- Which VA starts the conversation
- Whether handover (routing) can take place

### File paths ([paths.py](config/paths.py))

All file paths are defined here. Update when adding new databases and if you modify the directory structure.

---


## Populating the data_sources folder

The chatbot system requires knowledge base files and vector databases to function. This section explains how to use the [create_database.py](data_sources/create_database.py) file to generate your own databases.

*Note: The files that were used to create databases for the teacher, study adviser, and general VA are excluded from the repository due to the sensitive nature of the data.*

### General overview

Running [create_database.py](data_sources/create_database.py) does the following:

1. Scan `data_sources/Data/Context/` for all `.md` files
2. Scan for files ending in `*-folder_context.md`, of which the content is added to chunk metadata
3. Split documents into chunks (based on `MIN_CHARS` and `MAX_CHARS` in [config/tunables.py](config/tunables.py)) with metadata
4. Generate embeddings using model defined in [config/runtime.py](config/runtime.py)
5. Store chunks in ChromaDB vector databases in `data_sources/Database/Chroma_database_*`
6. Create overview markdown file showing all chunks for analysis in `data_sources/Database/`

### Data

Any used data files are required to be formatted and structured according to the following guidelines:

#### Use markdown

The database construction was built around detecting Markdown headers. This means that, in order to have the most logical cutoff points for the created chunks, **data files need to be in .md format**. An example of how to format .md files: [https://www.markdownguide.org/basic-syntax/](https://www.markdownguide.org/basic-syntax/)

#### Folder context

Folder context files named `*-folder_context.md` can be added to provide general information about a folder's contents. Any files that are in the same folder as the folder context file will have the folder context added to their resulting chunks. Folder context is added to each chunk to benefit the RAG system. If there are multiple folder context files within a folder (e.g., both in the main folder and within a subfolder), the system will select the first folder context file it comes across.

### Database

To use the [create_database.py](data_sources/create_database.py) file to generate your own Chroma databases, the following is required:

1. Upload `.md` files to the `data_sources/Data/Context/` folder
2. Upload any `*-folder_context.md` files if so desired
3. Ensure that the correct paths are defined in [create_database.py](data_sources/create_database.py)

A few database paths have already been defined. The system will ask which database to create when you run the script. 

If you want to add a new database type, update the following:
- `select_database_type()` in [create_database.py](data_sources/create_database.py)
- `DB_CONFIG` in [create_database.py](data_sources/create_database.py)
- Path config in [config/paths.py](config/paths.py)

4. Run the [run_database_creaation.py](run_database_creation.py) file and follow the instructions in the terminal

### Requirements

**Requirements for database generation:**
- Ollama must be running
- Selected embeddings model must be downloaded (see [Model Selection](#model-selection-runtimepy))
- Sufficient disk space needs to be available

### File structure

The file structure should be as follows:

```
data_sources/
├── create_database.py        ✅ Included
├── Data/                     ❌ NOT included in repository
│   └── Context/                        # .md files used to generate Chroma database
└── Database/                 ❌ NOT included in repository
    ├── *_chunks.md                     # .md files with all chunks for analysis purposes
    ├── Chroma_database_*/              # Chroma database(s) used for RAG
        └── [vector database files]
```

## Troubleshooting
- If you get the error `ModuleNotFoundError: No module named 'config'`, check whether you are using the correct file to run the application. Make sure to use the run_* file.
