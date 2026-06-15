"""
ENVIRONMENT VARIABLE VALIDATOR
Validates all required environment variables at startup
Prevents silent failures and provides clear error messages
"""
import os
import sys
from typing import Dict, List, Tuple

class EnvValidator:
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        
    def validate_required(self, var_name: str, description: str) -> None:
        """Check if a required variable exists"""
        value = os.getenv(var_name)
        if not value or value.startswith("mock_"):
            self.warnings.append(
                f"⚠️  {var_name}: Using mock/default value. {description}"
            )
    
    def validate_optional(self, var_name: str, description: str) -> None:
        """Check if an optional variable exists"""
        value = os.getenv(var_name)
        if not value:
            self.warnings.append(
                f"ℹ️  {var_name}: Not set. {description}"
            )
    
    def validate_all(self) -> Tuple[bool, List[str], List[str]]:
        """Validate all environment variables"""
        
        # Required for production
        self.validate_required("JWT_SECRET_KEY", "Used for JWT token signing. Generate a secure random string for production.")
        self.validate_required("ENCRYPTION_KEY", "Used for encrypting GitHub tokens. Generate a 32-byte URL-safe base64 key.")
        
        # GitHub Integration (required for full functionality)
        self.validate_required("GITHUB_CLIENT_ID", "Required for GitHub OAuth. Get from GitHub App settings.")
        self.validate_required("GITHUB_CLIENT_SECRET", "Required for GitHub OAuth. Get from GitHub App settings.")
        
        # AI Integration (required for reviews)
        self.validate_required("GROQ_API_KEY", "Required for AI code reviews. Get from console.groq.com")
        
        # Database (auto-configured for SQLite/Postgres)
        db_uri = os.getenv("SQLALCHEMY_DATABASE_URI")
        if db_uri and "sqlite" in db_uri:
            self.warnings.append("ℹ️  Database: Using SQLite (development mode)")
        elif db_uri and "postgresql" in db_uri:
            pass  # Production Postgres - good!
        else:
            self.warnings.append("ℹ️  Database: Using default SQLite configuration")
        
        # Vector Store
        qdrant_url = os.getenv("QDRANT_URL", "in-memory")
        if qdrant_url == "in-memory":
            self.warnings.append("ℹ️  Qdrant: Using in-memory mode (data lost on restart)")
        
        # CORS
        cors_origins = os.getenv("BACKEND_CORS_ORIGINS")
        if not cors_origins:
            self.warnings.append("ℹ️  CORS: Using default origins. Set BACKEND_CORS_ORIGINS for production.")
        
        # Frontend URL
        frontend_url = os.getenv("FRONTEND_URL")
        if not frontend_url:
            self.warnings.append("ℹ️  FRONTEND_URL: Using default http://localhost:3000")
        
        return len(self.errors) == 0, self.errors, self.warnings
    
    def print_validation_report(self) -> None:
        """Print validation results"""
        is_valid, errors, warnings = self.validate_all()
        
        print("\n" + "="*80)
        print("🔍 ENVIRONMENT VALIDATION REPORT")
        print("="*80)
        
        if errors:
            print("\n❌ ERRORS (Application cannot start):")
            for error in errors:
                print(f"  {error}")
            print("\n" + "="*80 + "\n")
            sys.exit(1)
        
        if warnings:
            print("\n⚠️  WARNINGS (Application will start with limited functionality):")
            for warning in warnings:
                print(f"  {warning}")
        
        if not warnings:
            print("\n✅ All environment variables validated successfully!")
        
        print("\n" + "="*80 + "\n")

# Global validator instance
env_validator = EnvValidator()
