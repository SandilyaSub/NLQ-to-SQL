# Movie Insights Explorer: NLQ to SQL Converter

A web-based application that converts natural language questions (NLQ) to SQL queries using a Retrieval-Augmented Generation (RAG) approach with the Together AI API. The system is optimized to query Google's public BigQuery IMDB dataset.

## Live Demo

Visit [Movie Insights Explorer](https://your-vercel-deployment-url.vercel.app) to try the application.

## Features

- **Natural Language to SQL Conversion**: Ask questions in plain English about movies, actors, and ratings
- **RAG-Enhanced Query Generation**: Uses a retrieval-augmented generation approach to optimize token usage and improve query accuracy
- **BigQuery IMDB Integration**: Seamlessly queries Google's public IMDB dataset
- **Interactive UI**: Clean, modern interface with collapsible sections for query results
- **User Feedback System**: Thumbs up/down feedback mechanism to improve future query processing
- **Query History**: Tracks previous questions for easy reference
- **Processing Logs**: Real-time visibility into the query processing steps

## Architecture

The system uses a multi-agent approach with:

1. **Data Analyst Agent**: Generates SQL queries from natural language questions
2. **Validation Agent**: Validates and refines the generated SQL
3. **SchemaRAG System**: Embeds and retrieves relevant schema information to optimize token usage

## Technical Stack

- **Backend**: Flask (Python)
- **Frontend**: HTML, CSS, JavaScript
- **Database**: Google BigQuery (IMDB public dataset)
- **AI Integration**: Together AI API for embeddings and LLM
- **Deployment**: Vercel

## Setup for Local Development

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/nlq-to-sql.git
   cd nlq-to-sql
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up your environment variables in a `.env` file:
   ```
   TOGETHER_API_KEY=your_together_api_key_here
   DB_TYPE=bigquery_imdb
   ```

4. Run the application:
   ```
   python app.py
   ```

5. Open your browser and navigate to `http://localhost:5724`

## Deployment on Vercel

This repository is configured for easy deployment on Vercel:

1. Fork this repository to your GitHub account
2. Connect your GitHub repository to Vercel
3. Add your `TOGETHER_API_KEY` as an environment variable in the Vercel project settings
4. Deploy!

## How It Works

1. The user submits a natural language question through the web interface
2. The SchemaRAG system retrieves relevant parts of the IMDB database schema
3. The Data Analyst Agent generates a SQL query based on the question and schema context
4. The Validation Agent checks the query for syntax errors and semantic correctness
5. If issues are found, the query is refined and validated again
6. The final query is executed against Google's BigQuery IMDB dataset
7. Results are displayed in the web interface
8. User feedback is collected to improve future query processing

## Example Questions

- "What are the top 10 highest-rated movies of all time?"
- "Who directed the most movies in the 1990s?"
- "What is the average rating of movies starring Tom Hanks?"
- "Which actors have appeared in the most movies with Leonardo DiCaprio?"
- "What was the most popular genre in the 2010s?"

## Feedback and Contributions

Feedback and contributions are welcome! Please feel free to submit issues or pull requests.
