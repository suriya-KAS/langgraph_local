"""
Test script for evaluating orchestrator category classification accuracy.

This script tests the LLM-based category classification by running
a set of test queries and comparing predicted categories with expected categories.
"""
import asyncio
import sys
import os
from typing import List, Tuple, Dict
from datetime import datetime

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.orchestrator.user_intent import get_orchestrator
from utils.logger_config import get_logger

logger = get_logger(__name__)


# Test questions with expected categories
TEST_QUESTIONS: List[Tuple[str, str]] = [
    # ANALYTICS questions (should be classified as "analytics_reporting")
    ("What are my sales today?", "analytics_reporting"),
    ("How are my ads performing?", "analytics_reporting"),
    ("Show ACOS across all platforms", "analytics_reporting"),
    ("Which products are low on inventory?", "analytics_reporting"),
    ("Compare Amazon vs Meta ad spend", "analytics_reporting"),
    ("Business health check", "analytics_reporting"),
    ("What are my sales today?", "analytics_reporting"),  # Duplicate for testing consistency
    ("Show revenue by product", "analytics_reporting"),
    ("Compare sales: last month vs this month", "analytics_reporting"),
    ("How are Meta ads performing?", "analytics_reporting"),
    ("Compare: Amazon ads vs Meta ads", "analytics_reporting"),
    ("Why is my ACOS increasing?", "analytics_reporting"),
    ("Which keywords are wasting budget?", "analytics_reporting"),
    ("Which products have missing attributes?", "analytics_reporting"),
    ("What are customers complaining about?", "analytics_reporting"),
    
    # Product Details questions (should be classified as "product_detail")
    ("How do I connect my Amazon account?", "product_detail"),
    ("What features do you offer?", "product_detail"),
    ("Can you track inventory?", "product_detail"),
    ("What's the difference between Pro and Enterprise?", "product_detail"),
    ("How much does this cost?", "product_detail"),
    ("Do you support Walmart?", "product_detail"),
    ("Can you help with Meta ads?", "product_detail"),
]


class ClassificationTester:
    """Test orchestrator classification accuracy."""
    
    def __init__(self):
        """Initialize the tester."""
        self.orchestrator = get_orchestrator()
        self.results: List[Dict] = []
    
    async def test_single_query(self, query: str, expected_category: str) -> Dict:
        """
        Test a single query and return results.
        
        Args:
            query: The test query
            expected_category: The expected category
            
        Returns:
            Dict with test results
        """
        try:
            logger.info(f"Testing query: {query}")
            logger.info(f"Expected category: {expected_category}")
            
            # Get predicted category
            predicted_category = await self.orchestrator.get_category_for_query(query)
            
            # Check if prediction matches expected
            is_correct = predicted_category == expected_category
            
            result = {
                "query": query,
                "expected": expected_category,
                "predicted": predicted_category,
                "correct": is_correct,
                "error": None
            }
            
            if is_correct:
                logger.info(f"✓ CORRECT: Predicted '{predicted_category}' (expected '{expected_category}')")
            else:
                logger.warning(f"✗ INCORRECT: Predicted '{predicted_category}' (expected '{expected_category}')")
            
            return result
            
        except Exception as e:
            logger.error(f"Error testing query '{query}': {e}", exc_info=True)
            return {
                "query": query,
                "expected": expected_category,
                "predicted": None,
                "correct": False,
                "error": str(e)
            }
    
    async def run_all_tests(self) -> Dict:
        """
        Run all test queries and calculate metrics.
        
        Returns:
            Dict with overall test results and metrics
        """
        logger.info("=" * 80)
        logger.info("Starting Orchestrator Classification Accuracy Test")
        logger.info("=" * 80)
        logger.info(f"Total test queries: {len(TEST_QUESTIONS)}")
        logger.info("")
        
        # Run all tests
        for i, (query, expected_category) in enumerate(TEST_QUESTIONS, 1):
            logger.info(f"\n[{i}/{len(TEST_QUESTIONS)}] Testing query...")
            result = await self.test_single_query(query, expected_category)
            self.results.append(result)
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.5)
        
        # Calculate metrics
        total = len(self.results)
        correct = sum(1 for r in self.results if r["correct"])
        incorrect = total - correct
        accuracy = (correct / total * 100) if total > 0 else 0
        
        # Group by category
        analytics_total = sum(1 for r in self.results if r["expected"] == "analytics_reporting")
        analytics_correct = sum(1 for r in self.results 
                               if r["expected"] == "analytics_reporting" and r["correct"])
        analytics_accuracy = (analytics_correct / analytics_total * 100) if analytics_total > 0 else 0
        
        product_total = sum(1 for r in self.results if r["expected"] == "product_detail")
        product_correct = sum(1 for r in self.results 
                            if r["expected"] == "product_detail" and r["correct"])
        product_accuracy = (product_correct / product_total * 100) if product_total > 0 else 0
        
        # Errors
        errors = [r for r in self.results if r["error"]]
        
        return {
            "total": total,
            "correct": correct,
            "incorrect": incorrect,
            "accuracy": accuracy,
            "analytics": {
                "total": analytics_total,
                "correct": analytics_correct,
                "accuracy": analytics_accuracy
            },
            "product_detail": {
                "total": product_total,
                "correct": product_correct,
                "accuracy": product_accuracy
            },
            "errors": len(errors),
            "results": self.results
        }
    
    def print_results(self, metrics: Dict):
        """
        Print test results in a formatted way.
        
        Args:
            metrics: Test metrics dictionary
        """
        print("\n" + "=" * 80)
        print("ORCHESTRATOR CLASSIFICATION TEST RESULTS")
        print("=" * 80)
        print(f"\nTest Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total Test Queries: {metrics['total']}")
        print(f"Correct Classifications: {metrics['correct']}")
        print(f"Incorrect Classifications: {metrics['incorrect']}")
        print(f"Errors: {metrics['errors']}")
        print(f"\n{'OVERALL ACCURACY':<30} {metrics['accuracy']:.2f}%")
        print(f"{'─' * 50}")
        
        print(f"\n{'CATEGORY BREAKDOWN':<30}")
        print(f"{'─' * 50}")
        print(f"{'Analytics Reporting':<30} {metrics['analytics']['correct']}/{metrics['analytics']['total']} ({metrics['analytics']['accuracy']:.2f}%)")
        print(f"{'Product Detail':<30} {metrics['product_detail']['correct']}/{metrics['product_detail']['total']} ({metrics['product_detail']['accuracy']:.2f}%)")
        
        # Show incorrect predictions
        incorrect_results = [r for r in metrics['results'] if not r['correct']]
        if incorrect_results:
            print(f"\n{'INCORRECT CLASSIFICATIONS':<30}")
            print(f"{'─' * 80}")
            for result in incorrect_results:
                print(f"\nQuery: {result['query']}")
                print(f"  Expected: {result['expected']}")
                print(f"  Predicted: {result['predicted']}")
                if result['error']:
                    print(f"  Error: {result['error']}")
        
        # Show errors
        error_results = [r for r in metrics['results'] if r['error']]
        if error_results:
            print(f"\n{'ERRORS':<30}")
            print(f"{'─' * 80}")
            for result in error_results:
                print(f"\nQuery: {result['query']}")
                print(f"  Error: {result['error']}")
        
        # Detailed results table
        print(f"\n{'DETAILED RESULTS':<30}")
        print(f"{'─' * 80}")
        print(f"{'#':<4} {'Status':<10} {'Expected':<20} {'Predicted':<20} {'Query'}")
        print(f"{'─' * 80}")
        
        for i, result in enumerate(metrics['results'], 1):
            status = "✓" if result['correct'] else "✗"
            expected = result['expected']
            predicted = result['predicted'] or "ERROR"
            query = result['query'][:40] + "..." if len(result['query']) > 40 else result['query']
            print(f"{i:<4} {status:<10} {expected:<20} {predicted:<20} {query}")
        
        print("\n" + "=" * 80)


async def main():
    """Main test function."""
    tester = ClassificationTester()
    metrics = await tester.run_all_tests()
    tester.print_results(metrics)
    
    # Return exit code based on accuracy
    if metrics['accuracy'] >= 90:
        print("\n✓ Excellent accuracy! (≥90%)")
        return 0
    elif metrics['accuracy'] >= 75:
        print("\n⚠ Good accuracy, but could be improved (75-90%)")
        return 0
    else:
        print("\n✗ Accuracy needs improvement (<75%)")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error in test script: {e}", exc_info=True)
        print(f"\n\nFatal error: {e}")
        sys.exit(1)

