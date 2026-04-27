from wanted_crawler import main as crawl
from recommender import main as recommend


def main():
    new_jobs = crawl()
    recommend(new_jobs)


if __name__ == "__main__":
    main()
