import pandas as pd
import hashlib
from faker import Faker

# Initialize Synthetic Data Generator
fake = Faker()

class DataAnonymizer:
    def __init__(self, df):
        self.df = df.copy()

    def redact_column(self, column):
        """Replaces values with a [REDACTED] label."""
        self.df[column] = "[REDACTED]"
        
    def hash_column(self, column):
        """Deterministic hashing for ID preservation."""
        self.df[column] = self.df[column].apply(
            lambda x: hashlib.sha256(str(x).encode()).hexdigest()[:12]
        )

    def synthesize_name(self, column):
        """Generates realistic but fake names."""
        self.df[column] = [fake.name() for _ in range(len(self.df))]

    def blur_age(self, column):
        """Applies bucketing to numerical data."""
        self.df[column] = self.df[column].apply(lambda x: f"{(x // 10) * 10}s")

# Example Usage Implementation
if __name__ == "__main__":
    # 1. Load Sample Data
    raw_data = {
        'user_id': [101, 102, 103],
        'full_name': ['John Doe', 'Jane Smith', 'Carlos Ruiz'],
        'email': ['john@example.com', 'jane@test.com', 'carlos@web.com'],
        'age': [28, 34, 45]
    }
    df = pd.DataFrame(raw_data)
    
    # 2. Apply Privacy Layer
    engine = DataAnonymizer(df)
    engine.hash_column('user_id')      # Protect IDs
    engine.synthesize_name('full_name') # Replace Names
    engine.redact_column('email')      # Remove Emails
    engine.blur_age('age')             # Bucket Ages

    # 3. Secure Output
    print("--- Original Data Preview ---")
    print(pd.DataFrame(raw_data).head())
    print("\n--- Masked Data (Sentinel Output) ---")
    print(engine.df.head())
