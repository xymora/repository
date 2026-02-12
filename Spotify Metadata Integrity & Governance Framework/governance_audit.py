import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# --- CONFIGURATION & UI SETUP ---
plt.style.use('ggplot')
BANNER = "║" + "═"*68 + "║"
TIMESTAMP = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def print_header(title):
    print(f"\n{BANNER}")
    print(f"║ SPOTIFY DATA GOVERNANCE: {title.center(42)} ║")
    print(f"║ Generated at: {TIMESTAMP.center(49)} ║")
    print(f"{BANNER}\n")

# --- DATA ACQUISITION ---
def load_spotify_data():
    """Retrieval from verified public Data Science repository"""
    url = "https://raw.githubusercontent.com/rfordatascience/tidytuesday/master/data/2020/2020-01-21/spotify_songs.csv"
    try:
        df = pd.read_csv(url)
        return df
    except Exception as e:
        print(f" [X] Critical Error loading data: {e}")
        return None

# --- GOVERNANCE CORE MODULES ---
class DataGovernanceAudit:
    def __init__(self, dataframe):
        self.df = dataframe
        self.quality_report = {}

    def run_profiling(self):
        """Checks for completeness and data integrity"""
        print_header("DATA PROFILING & INTEGRITY CHECK")
        
        # Missing values analysis
        missing = self.df.isnull().sum()
        self.quality_report['null_count'] = missing.sum()
        
        print(f" [✓] Total records audited: {len(self.df)}")
        print(f" [!] Missing values detected: {missing.sum()}")
        print("\n   > Breakdown by metadata field:")
        for col, val in missing[missing > 0].items():
            print(f"     - {col.ljust(20)}: {val} nulls")

    def validate_business_rules(self):
        """Ensures audio features are within legal/logical bounds [0, 1]"""
        print_header("BUSINESS RULE VALIDATION")
        
        rules = ['danceability', 'energy', 'speechiness', 'acousticness', 'instrumentalness', 'liveness', 'valence']
        outliers = {}
        
        print(" [!] Audit Status per Metric:")
        for feature in rules:
            invalid = self.df[(self.df[feature] < 0) | (self.df[feature] > 1)]
            outliers[feature] = len(invalid)
            status = " [ PASS ] " if len(invalid) == 0 else " [ FAIL ] "
            print(f"   {status} {feature.capitalize().ljust(18)} | Violations: {len(invalid)}")

    def generate_governance_dashboard(self):
        """Visual representation of Catalog Health for Decision Making"""
        print_header("GENERATING EXECUTIVE DASHBOARD")
        
        # 1. Distribution of Catalog by Genre
        genre_dist = self.df['playlist_genre'].value_counts()
        fig = px.pie(values=genre_dist.values, names=genre_dist.index, 
                     title="Catalog Distribution by Genre (Governance View)",
                     color_discrete_sequence=px.colors.sequential.Greens_r,
                     hole=0.4)
        fig.update_layout(template="plotly_dark")
        fig.show()

        # 2. Correlation Matrix: Metadata Dependencies
        plt.figure(figsize=(12, 7))
        corr = self.df[['track_popularity', 'danceability', 'energy', 'loudness', 'tempo']].corr()
        mask = np.triu(np.ones_like(corr, dtype=bool))
        sns.heatmap(corr, mask=mask, annot=True, cmap='coolwarm', center=0)
        plt.title("Metadata Correlation Map (Audit Standard v2.1)")
        plt.show()

        # 3. Interactive Market Trend Analysis
        fig2 = px.scatter(self.df.sample(2000), x="energy", y="track_popularity", 
                         color="playlist_genre", size="danceability",
                         hover_data=['track_name', 'track_artist'],
                         title="Market Trend: Popularity vs. Energy Distribution")
        fig2.update_layout(template="plotly_dark")
        fig2.show()

    def provide_strategic_recommendations(self):
        """Automated insights for the Chief Data Officer (CDO)"""
        print_header("STRATEGIC RECOMMENDATIONS")
        
        avg_pop = self.df['track_popularity'].mean()
        top_genre = self.df['playlist_genre'].value_counts().idxmax()
        
        print(f" 1. 📊 MARKET ANALYSIS: The '{top_genre}' genre dominates the current data pull.")
        print(f" 2. ⭐ QUALITY SCORE: Catalog Popularity average is {avg_pop:.2f}/100.")
        
        if self.quality_report['null_count'] > 0:
            print(" 3. ⚠️ ACTION REQUIRED: Immediate metadata scrubbing needed in null fields.")
        else:
            print(" 3. ✅ DATA HEALTH: Asset integrity scores are within Tier-1 thresholds.")
        
        print(f"\n{BANNER}")

# --- EXECUTION ---
if __name__ == "__main__":
    raw_data = load_spotify_data()
    
    if raw_data is not None:
        audit = DataGovernanceAudit(raw_data)
        audit.run_profiling()
        audit.validate_business_rules()
        audit.generate_governance_dashboard()
        audit.provide_strategic_recommendations()
    else:
        print(" [X] Initialization Failed: Could not connect to Data Source.")
