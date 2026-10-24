# Datasets

## MovieLens

- **Provider:** GroupLens Research, Department of Computer Science and Engineering, University of Minnesota
- **URL:** https://grouplens.org/datasets/movielens/
- **Variants used:**
  - **MovieLens 100K (`ml-100k`):** 100,000 ratings (scale 1–5) from 943 users across 1,682 movies; each user has rated at least 20 movies; released 1998. Used for `--fast` development mode and unit/integration tests.
  - **MovieLens 1M (`ml-1m`):** 1,000,209 ratings (scale 1–5) from 6,040 users across 3,706 movies; released 2003. Used for final benchmark results, hyperparameter selection, and production artifacts.
- **License:** Research and educational use only; non-commercial.
- **Citation:**
  > Harper, F.M. and Konstan, J.A. (2015). The MovieLens Datasets: History and Context. ACM Transactions on Interactive Intelligent Systems (TiiS), 5(4), Article 19. https://doi.org/10.1145/2827872
- **Terms:**
  - The University of Minnesota and its researchers provide the data without warranty of correctness or fitness for any purpose.
  - Users may not redistribute or make available any portion of the dataset without express permission.
  - Commercial use is strictly prohibited.
  - GroupLens and the ACM reference above must be acknowledged and cited in all publications, reports, or demo presentations.
- **Data location:** `data/raw/movielens/` (contains `ml-100k/` and `ml-1m/`).
- **Files per variant:**
  - `ml-100k/`: `u.data` (tab-separated: user id, item id, rating, timestamp), `u.item` (pipe-separated: movie id, title with year, release date, IMDb URL, 19 genre flags).
  - `ml-1m/`: `ratings.dat` (`::`-separated: UserID, MovieID, Rating, Timestamp), `movies.dat` (`::`-separated: MovieID, Title with year, Genres separated by `|`).

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
