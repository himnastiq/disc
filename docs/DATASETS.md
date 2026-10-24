# Datasets

## MovieLens

- **Provider:** GroupLens Research, University of Minnesota
- **URL:** https://grouplens.org/datasets/movielens/
- **Variants used:** MovieLens 100K (fast/test), MovieLens 1M (final results)
- **License:** Research and education use only; non-commercial
- **Citation:**
  > Harper, F.M. and Konstan, J.A. (2015). The MovieLens Datasets: History and Context. ACM Transactions on Interactive Intelligent Systems (TiiS), 5(4), Article 19.
- **Terms:** <!-- TODO: verify current terms when downloading -->
- **Data location:** `data/raw/movielens/`

## Amazon Reviews

- **Provider:** Amazon / UCSD
- **URL:** <!-- TODO: fill in after P4.1 dataset decision -->
- **Variant used:** <!-- TODO: fill in after P4.1 -->
- **License:** Academic use only
- **Citation:** <!-- TODO: fill in after P4.1 -->
- **Terms:** <!-- TODO: verify current terms when downloading -->
- **Data location:** `data/raw/amazon/`

## MIND (Microsoft News Dataset)

- **Provider:** Microsoft Research
- **URL:** https://msnews.github.io/
- **Variant used:** MIND-small (train + dev)
- **License:** Microsoft Research License (research use)
- **Citation:**
  > Wu, F., Qiao, Y., Chen, J.-H., Wu, C., Qi, T., Lian, J., Liu, D., Xie, X., Gao, J., Wu, W., & Zhou, M. (2020). MIND: A Large-scale Dataset for News Recommendation. Proceedings of the 58th Annual Meeting of the Association for Computational Linguistics (ACL), 3597–3606.
- **Terms:** <!-- TODO: verify current terms when downloading -->
- **Data location:** `data/raw/mind/`

---

## General Notes

- Raw datasets are **not committed** to the repository (listed in `.gitignore`).
- Use `make data` or `python backend/scripts/fetch_data.py` to download.
- If automatic download fails, `fetch_data.py` prints manual download instructions.
