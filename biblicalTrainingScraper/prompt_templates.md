# Prompt Templates for Course Study Help

This file contains prompt templates for both Notebook LLM workflows and RAG workflows.

## Notebook LLM Prompt Templates

### 1. Course Study Guide Generator

```text
Read the course markdown and create a study guide for this class.

For each lesson:
1. Write a concise lesson summary.
2. Extract the main outline points as a numbered list.
3. Identify key terms, topics, or Scripture references mentioned.
4. Generate one suggested study question for the lesson.

Use only the text from the course markdown. Do not invent details.
```

### 2. Lesson Question Answering

```text
Use the course markdown to answer the user question below.

Question:
<insert question here>

Answer clearly and directly using only information from the lesson transcripts and course content. If the document does not cover it, say "Not covered in this course."
```

### 3. Course Summary + Sample Questions

```text
I want a structured study guide from the course markdown.

1. Summarize the course purpose and instructor details.
2. For each lesson, give a short summary and the main outline topics.
3. Generate 3 example study questions based on the lesson content.
4. Answer this sample question using only the document text:
   "<insert sample question>"

Provide the output as structured text.
```

## RAG Prompt Templates

### 1. RAG Study Guide Instruction

```text
You are a study assistant using retrieved passages from a course document.

Based on the retrieved text:
1. Generate a concise study summary for the course.
2. Create a numbered lesson outline for each lesson.
3. Identify the most important concepts and terms.
4. Provide one or two study questions with short answers.

Only use the retrieved passages. If the answer is not contained in them, say "Not covered in this course."
```

### 2. RAG Question Answering

```text
Use the retrieved course passages to answer the question below.

Question:
<insert question here>

Answer directly from the text. If the information is missing, say "Not covered in this course."
```

### 3. RAG Retrieval Instructions

```text
Retrieve the most relevant passages from the course documents for the following task.

Task:
- Identify the lesson content that best answers this question.
- Return only the passages needed to answer it.
```

## Notes on RAG Resource Use

### How intensive is RAG?

- RAG is more resource intensive than a single notebook prompt because it stores embeddings and runs similarity search.
- For a decent laptop, a small local RAG system is usually manageable, especially if you keep individual course files small.

### Typical storage requirements

- Text file storage: course markdown files are small, usually a few megabytes each.
- Vector index storage: depends on the embedding dimension and number of chunks.
  - Example: a 1536-dimensional embedding with 10,000 chunks can use under 200 MB.
  - Smaller collections of transcripts are much lighter.
- Model storage: if you use a local open-source model, that can be the biggest requirement.
  - Small models can fit in a few GB.
  - Larger models may need 10+ GB and faster storage.

### What to consider on your laptop

- Use smaller models and embeddings first.
- Keep chunk sizes around 200–400 words for best retrieval accuracy.
- Index only what you need per course.
- If you want to scale later, move the index to a dedicated machine or cloud storage.

## Recommended workflow

1. Generate clean course markdown using `multipleClasses_notebook.py`.
2. Load the markdown into Notebook LLM or a RAG pipeline.
3. Compare the results for your prompts.
4. If you want more accurate answers across many courses, RAG is usually a better long-term choice.

---

This file can be committed to the repository for reference and reuse.