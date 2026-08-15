# Cross-Lingual Dense Retrieval System

**Student:** Harshita Singh  
**Registration:** 235816144  
**Class:** DS-D  
**Subject:** Information Retrieval

---

## Project Overview

A sophisticated information retrieval system that enables users to search for documents across multiple languages (English, Spanish, French) without explicit translation. Uses state-of-the-art multilingual transformers and dense retrieval techniques.

### Key Features
- ✅ Cross-lingual document retrieval (query in one language, retrieve in all)
- ✅ Dense retrieval using multilingual embeddings (mBERT, XLM-RoBERTa)
- ✅ Efficient vector search with FAISS
- ✅ Comprehensive evaluation metrics (MRR, Recall@k, nDCG)
- ✅ Interactive web demo with Streamlit
- ✅ Baseline comparison (BM25, Translate-Test)

### Dataset Size
- **Target:** 5,000-10,000 documents per language
- **Total:** ~15,000-30,000 documents
- **Sources:** Wikipedia, News articles

---

## Project Structure

```
cross_lingual_retrieval/
├── data/
│   ├── raw/                    # Original downloaded data
│   ├── processed/              # Cleaned and preprocessed data
│   └── embeddings/             # Stored document vectors
├── models/                     # Downloaded pre-trained models
├── src/
│   ├── data_collection.py      # Wikipedia/news scraping
│   ├── preprocessing.py        # Text cleaning and preparation
│   ├── baseline.py             # BM25 and translate-test baselines
│   ├── dense_retrieval.py      # Main dense retrieval implementation
│   ├── evaluation.py           # Metrics calculation
│   └── utils.py                # Helper functions
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_baseline_experiments.ipynb
│   └── 03_dense_retrieval_experiments.ipynb
├── web_app/
│   └── streamlit_app.py        # Interactive demo
├── results/                    # Evaluation results and plots
├── docs/                       # Documentation
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

---

## Tech Stack

- **Language:** Python 3.8+
- **ML Framework:** PyTorch
- **Transformers:** Hugging Face Transformers, Sentence-Transformers
- **Vector Search:** FAISS
- **Baseline:** Rank-BM25
- **Translation:** deep-translator
- **Web Framework:** Streamlit
- **Data Processing:** pandas, NumPy
- **Visualization:** matplotlib, seaborn, plotly

---

## Installation & Setup

### Step 1: Clone/Download Project
```bash
# If you have this as a zip, extract it
# Navigate to project directory
cd cross_lingual_retrieval
```

### Step 2: Create Virtual Environment (Recommended)
```bash
# Create virtual environment
python -m venv venv

# Activate it
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Verify Installation
```bash
python -c "import torch; import transformers; import faiss; print('All dependencies installed successfully!')"
```

---

## Usage Guide

### Phase 1: Data Collection (Week 1-2)

**Collect Wikipedia articles:**
```bash
python src/data_collection.py --languages en es fr --articles-per-lang 5000
```

This will download ~5,000 articles per language and save them in `data/raw/`.

**What you'll see:**
- Progress bars showing download status
- Articles saved as JSON files
- Total: ~15,000 articles

**Time required:** 2-4 hours (depending on internet speed)

---

### Phase 2: Preprocessing (Week 2)

**Clean and prepare data:**
```bash
python src/preprocessing.py --input data/raw --output data/processed
```

**What this does:**
- Removes HTML tags and special characters
- Filters out very short/long documents
- Creates train/test splits
- Saves as CSV files

**Output:** Clean, structured data ready for encoding

---

### Phase 3: Baseline Implementation (Week 3-4)

**Run BM25 baseline:**
```bash
python src/baseline.py --method bm25 --test-queries 100
```

**Run Translate-Test baseline:**
```bash
python src/baseline.py --method translate --test-queries 100
```

**What you'll get:**
- Baseline retrieval results
- Performance metrics
- Saved in `results/baseline/`

---

### Phase 4: Dense Retrieval (Week 5-7)

**Encode all documents:**
```bash
python src/dense_retrieval.py --mode encode --model sentence-transformers/LaBSE
```

**This will:**
- Load the multilingual model
- Encode all 15K-30K documents
- Save embeddings to `data/embeddings/`

**Time required:** 1-3 hours (GPU) or 6-12 hours (CPU)

**Build FAISS index:**
```bash
python src/dense_retrieval.py --mode index
```

**Search with queries:**
```bash
python src/dense_retrieval.py --mode search --query "climate change solutions"
```

---

### Phase 5: Evaluation (Week 8-9)

**Run comprehensive evaluation:**
```bash
python src/evaluation.py --baseline-results results/baseline --dense-results results/dense
```

**Generates:**
- MRR, Recall@5, Recall@10, nDCG scores
- Comparison plots
- Per-language performance breakdown
- Saved in `results/evaluation/`

---

### Phase 6: Web Demo (Week 10)

**Launch interactive demo:**
```bash
streamlit run web_app/streamlit_app.py
```

**Opens in browser:** http://localhost:8501

**Features:**
- Search box (type in any language)
- Results from all languages
- Highlight relevant snippets
- Performance metrics display

---

## Evaluation Metrics Explained

### 1. Mean Reciprocal Rank (MRR)
- Measures rank of first relevant result
- Range: 0 to 1 (higher is better)
- Example: First relevant result at position 3 → 1/3 = 0.33

### 2. Recall@k
- Percentage of relevant docs found in top-k results
- Recall@10 = "Did we find it in top 10?"
- Range: 0 to 1 (higher is better)

### 3. nDCG (Normalized Discounted Cumulative Gain)
- Measures quality of ranking
- Rewards relevant docs appearing higher
- Range: 0 to 1 (higher is better)

---

## Expected Results

Based on research benchmarks, you should see:

| Method | MRR | Recall@10 | nDCG@10 |
|--------|-----|-----------|---------|
| BM25 (monolingual) | 0.45 | 0.62 | 0.58 |
| Translate-Test | 0.52 | 0.68 | 0.64 |
| **Dense Retrieval (LaBSE)** | **0.68** | **0.82** | **0.78** |

*Note: Actual results depend on dataset quality and test queries*

---

## Troubleshooting

### Issue: Out of Memory during encoding
**Solution:** Process in smaller batches
```bash
python src/dense_retrieval.py --mode encode --batch-size 16
```

### Issue: FAISS installation fails
**Solution:** Install CPU version
```bash
pip install faiss-cpu
```

### Issue: Slow encoding on CPU
**Solution:** Use Google Colab (free GPU)
- Upload notebook to Colab
- Run encoding there
- Download embeddings

### Issue: Wikipedia download fails
**Solution:** Reduce articles per language
```bash
python src/data_collection.py --articles-per-lang 2000
```

---

## Project Timeline

- ✅ **Week 1-2:** Data collection and preprocessing
- ✅ **Week 3-4:** Baseline implementation
- ✅ **Week 5-7:** Dense retrieval pipeline
- ✅ **Week 8-9:** Evaluation and analysis
- ✅ **Week 10:** Web demo development
- ✅ **Week 11-12:** Documentation and presentation

---

## Future Enhancements (Optional)

If you finish early or want to go beyond:

1. **Add more languages** (German, Hindi, Arabic)
2. **Fine-tune models** on parallel corpora
3. **Implement re-ranking** with cross-encoders
4. **Add query expansion** techniques
5. **Optimize for speed** (quantization, GPU deployment)
6. **Create REST API** for production use

---

## References & Resources

### Papers
- "Making Monolingual Sentence Embeddings Multilingual using Knowledge Distillation" (LaBSE)
- "Unsupervised Cross-lingual Representation Learning at Scale" (XLM-RoBERTa)
- "Dense Passage Retrieval for Open-Domain Question Answering" (DPR)

### Documentation
- [Sentence-Transformers](https://www.sbert.net/)
- [FAISS](https://github.com/facebookresearch/faiss)
- [Hugging Face Transformers](https://huggingface.co/docs/transformers)

---

## Contact & Support

**Student:** Harshita Singh  
**Email:** [Your Email]  
**GitHub:** [Your GitHub]

---

## License

This project is for educational purposes (Information Retrieval course project).

---

**Good luck building this impressive project! 🚀**
