# Quick Start Guide - Cross-Lingual Retrieval System

## 🚀 Getting Started in 5 Minutes

### Step 1: Setup Environment

```bash
# Navigate to project directory
cd cross_lingual_retrieval

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**Note:** This will take 5-10 minutes on first install.

---

### Step 2: Collect Data (Optional - Use Sample Dataset)

For a quick demo, you can start with a smaller dataset:

```bash
# Collect 1000 articles per language (faster for testing)
python src/data_collection.py --articles-per-lang 1000
```

**Time:** ~30-60 minutes

For the full impressive dataset (5000+ per language):
```bash
python src/data_collection.py --articles-per-lang 5000
```

**Time:** ~2-4 hours

---

### Step 3: Preprocess Data

```bash
python src/preprocessing.py
```

**Time:** ~2-5 minutes

**What you get:**
- Clean, structured CSV files
- Train/test splits
- Test queries for evaluation

---

### Step 4: Run Dense Retrieval (The Cool Part!)

```bash
# Encode documents and build index
python src/dense_retrieval.py --mode all --batch-size 32
```

**Time:** 
- CPU: 1-3 hours (for 3000 docs) or 4-8 hours (for 15000 docs)
- GPU: 15-30 minutes (for 3000 docs) or 45-90 minutes (for 15000 docs)

**Pro Tip:** Use Google Colab for free GPU! 
1. Upload the notebook from `notebooks/`
2. Run encoding there
3. Download embeddings

---

### Step 5: Launch Web Demo

```bash
streamlit run web_app/streamlit_app.py
```

Opens automatically in your browser at `http://localhost:8501`

**Try searching in different languages!**

---

## 📊 Quick Evaluation

Compare all methods:

```bash
# Run baseline first
python src/baseline.py --method both --test-queries 100

# Dense retrieval evaluation (if not done in Step 4)
python src/dense_retrieval.py --mode evaluate --test-queries 100

# Generate comparison
python src/evaluation.py
```

---

## 🎯 Quick Demo Workflow

For a quick demo in ~1 hour (small dataset):

```bash
# 1. Collect small dataset
python src/data_collection.py --articles-per-lang 500

# 2. Preprocess
python src/preprocessing.py

# 3. Dense retrieval
python src/dense_retrieval.py --mode all --test-queries 50

# 4. Launch demo
streamlit run web_app/streamlit_app.py
```

---

## 💡 Tips for Success

### If you have limited time:
1. Start with 500-1000 articles per language
2. Use Google Colab for encoding (free GPU)
3. Focus on dense retrieval demo
4. Run baseline later for comparison

### If you have GPU access:
1. Go for full 5000+ articles per language
2. Use larger batch size (--batch-size 64 or 128)
3. Run comprehensive evaluation

### If you're on CPU only:
1. Start small (1000 articles per language)
2. Use batch size 16-32
3. Let encoding run overnight
4. Cache embeddings (they're reused!)

---

## 🐛 Common Issues

### "Out of Memory" during encoding
```bash
python src/dense_retrieval.py --mode encode --batch-size 8
```
Use smaller batch size.

### "FAISS not found"
```bash
pip install faiss-cpu
```

### Wikipedia download slow/failing
Reduce article count or run multiple times to collect incrementally.

### Streamlit won't start
Make sure you're in project directory and venv is activated.

---

## 📱 Project Structure at a Glance

```
cross_lingual_retrieval/
├── data/
│   ├── raw/          # Downloaded Wikipedia articles
│   ├── processed/    # Clean CSV files
│   └── embeddings/   # Encoded vectors (created during Step 4)
├── src/              # All Python scripts
├── web_app/          # Streamlit demo
├── results/          # Evaluation results
└── requirements.txt  # Dependencies
```

---

## ✅ Success Checklist

- [ ] Environment setup complete
- [ ] Data collected (at least 500+ per language)
- [ ] Data preprocessed
- [ ] Dense retrieval working
- [ ] Web demo running
- [ ] Baseline comparison done
- [ ] Evaluation plots generated

---

## 🎓 For Your Resume

Once complete, you have:
- ✅ Cross-lingual IR system (English, Spanish, French)
- ✅ Dataset of 1,500-30,000 documents
- ✅ Multilingual embeddings implementation
- ✅ FAISS vector search
- ✅ Evaluation with proper metrics
- ✅ Interactive web demo
- ✅ Comprehensive comparisons

**This is portfolio-worthy!**

---

## 📚 Next Steps

1. **Improve Results:** Try different models (XLM-R, mBERT)
2. **Add Features:** Query expansion, re-ranking
3. **Scale Up:** More languages, larger dataset
4. **Deploy:** Put on Hugging Face Spaces or Streamlit Cloud

---

## 🆘 Need Help?

Check the main README.md for detailed documentation on each component.

**Happy Building! 🚀**
