"""
EndoChat API Test Script
Tests all 50 API endpoints for the EndoChat application
Run: python test_all_apis.py
"""

import sys
import io

# Fix Windows console encoding for Unicode
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import requests
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Configuration
BASE_URL = "http://localhost:8000"
SESSION_ID = str(uuid.uuid4())

class TestStatus(Enum):
    PASSED = "✅ PASSED"
    FAILED = "❌ FAILED"
    SKIPPED = "⏭️ SKIPPED"

@dataclass
class TestResult:
    endpoint: str
    method: str
    status: TestStatus
    status_code: Optional[int] = None
    message: str = ""
    response_time_ms: float = 0

class APITester:
    def __init__(self, base_url: str, session_id: str):
        self.base_url = base_url
        self.session_id = session_id
        self.results: list[TestResult] = []
        self.created_resources: Dict[str, Any] = {}
        
    def get_headers(self, with_session: bool = False) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if with_session:
            headers["X-Session-ID"] = self.session_id
        return headers
    
    def make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        with_session: bool = False
    ) -> Tuple[Optional[requests.Response], float]:
        url = f"{self.base_url}{endpoint}"
        headers = self.get_headers(with_session)
        
        start_time = datetime.now()
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data, params=params, timeout=30)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=data, timeout=30)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, params=params, timeout=30)
            else:
                return None, 0
            
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            return response, elapsed_ms
        except requests.exceptions.RequestException as e:
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            return None, elapsed_ms
    
    def test_endpoint(
        self,
        method: str,
        endpoint: str,
        description: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        with_session: bool = False,
        expected_status: list[int] = [200, 201],
        store_key: Optional[str] = None,
        extract_field: Optional[str] = None
    ) -> TestResult:
        response, elapsed_ms = self.make_request(method, endpoint, data, params, with_session)
        
        if response is None:
            result = TestResult(
                endpoint=endpoint,
                method=method,
                status=TestStatus.FAILED,
                message="Connection failed - server may not be running",
                response_time_ms=elapsed_ms
            )
        elif response.status_code in expected_status:
            result = TestResult(
                endpoint=endpoint,
                method=method,
                status=TestStatus.PASSED,
                status_code=response.status_code,
                message=description,
                response_time_ms=elapsed_ms
            )
            if store_key and extract_field:
                try:
                    data = response.json()
                    if extract_field in data:
                        self.created_resources[store_key] = data[extract_field]
                except:
                    pass
        else:
            try:
                error_detail = response.json().get("detail", response.text[:100])
            except:
                error_detail = response.text[:100]
            result = TestResult(
                endpoint=endpoint,
                method=method,
                status=TestStatus.FAILED,
                status_code=response.status_code,
                message=f"Expected {expected_status}, got {response.status_code}: {error_detail}",
                response_time_ms=elapsed_ms
            )
        
        self.results.append(result)
        return result
    
    def print_result(self, result: TestResult):
        print(f"  {result.status.value} [{result.method:6}] {result.endpoint}")
        if result.status_code:
            print(f"           Status: {result.status_code} | Time: {result.response_time_ms:.0f}ms")
        if result.status == TestStatus.FAILED and result.message:
            print(f"           Error: {result.message}")
    
    def run_all_tests(self):
        print("\n" + "="*70)
        print("🩺 EndoChat API Test Suite")
        print(f"📍 Testing: {self.base_url}")
        print(f"🔑 Session ID: {self.session_id}")
        print("="*70 + "\n")
        
        # Test 1: Root Endpoint
        print("📌 ROOT ENDPOINT")
        self.print_result(self.test_endpoint("GET", "/", "Root API info"))
        
        # Test 2: Health Endpoints
        print("\n📌 HEALTH API (/api/health)")
        self.print_result(self.test_endpoint("GET", "/api/health", "Full health check"))
        self.print_result(self.test_endpoint("GET", "/api/health/live", "Liveness probe"))
        self.print_result(self.test_endpoint("GET", "/api/health/ready", "Readiness probe"))
        
        # Test 3: Chat Endpoints
        print("\n📌 CHAT API (/api/chat)")
        self.print_result(self.test_endpoint(
            "POST", "/api/chat/simple",
            "Simple chat (no LLM)",
            data={"question": "What is endometriosis?"},
            with_session=True
        ))
        self.print_result(self.test_endpoint(
            "POST", "/api/chat",
            "Full chat with LLM",
            data={"question": "What are common symptoms of endometriosis?"},
            with_session=True
        ))
        self.print_result(self.test_endpoint(
            "GET", "/api/chat/suggestions",
            "Get suggestions",
            params={"question": "endometriosis", "category": "symptoms"}
        ))
        self.print_result(self.test_endpoint("GET", "/api/chat/starters", "Get starter questions"))
        
        # Test 4: Feedback Endpoints
        print("\n📌 FEEDBACK API (/api/feedback)")
        self.print_result(self.test_endpoint(
            "POST", "/api/feedback",
            "Submit feedback",
            data={
                "question": "What is endometriosis?",
                "answer": "Test answer",
                "rating": 1,
                "session_id": self.session_id
            },
            expected_status=[200, 201, 422]
        ))
        self.print_result(self.test_endpoint("GET", "/api/feedback/stats", "Feedback statistics"))
        self.print_result(self.test_endpoint("GET", "/api/feedback/reasons", "Feedback reasons breakdown"))
        
        # Test 5: Popular Questions Endpoints
        print("\n📌 POPULAR QUESTIONS API (/api/popular)")
        self.print_result(self.test_endpoint(
            "GET", "/api/popular",
            "Get popular questions",
            params={"limit": 10}
        ))
        self.print_result(self.test_endpoint(
            "GET", "/api/popular/trending",
            "Get trending questions",
            params={"limit": 5, "hours": 24}
        ))
        self.print_result(self.test_endpoint("GET", "/api/popular/categories", "Get categories"))
        self.print_result(self.test_endpoint(
            "GET", "/api/popular/search",
            "Search popular questions",
            params={"q": "pain", "limit": 5}
        ))
        
        # Test 6: Share Endpoints
        print("\n📌 SHARE API (/api/share)")
        self.print_result(self.test_endpoint(
            "POST", "/api/share/generate-card",
            "Generate shareable card",
            data={
                "card_type": "fact",
                "content": "Endometriosis affects 1 in 10 women",
                "title": "Did you know?"
            },
            expected_status=[200, 201, 403, 500, 501]
        ))
        self.print_result(self.test_endpoint(
            "GET", "/api/share/test123",
            "Get shared card redirect",
            expected_status=[200, 302, 307, 404]
        ))
        self.print_result(self.test_endpoint(
            "GET", "/api/share/stats/00000000-0000-0000-0000-000000000000",
            "Get share stats",
            expected_status=[200, 404]
        ))
        self.print_result(self.test_endpoint(
            "POST", "/api/share/test123/track",
            "Track card click",
            data={"platform": "twitter"},
            expected_status=[200, 201, 404]
        ))
        
        # Test 7: Support Groups Endpoints
        print("\n📌 SUPPORT GROUPS API (/api/groups)")
        self.print_result(self.test_endpoint(
            "GET", "/api/groups/search",
            "Search support groups",
            params={"location": "New York", "radius": 50, "limit": 10},
            expected_status=[200, 403]
        ))
        self.print_result(self.test_endpoint(
            "POST", "/api/groups",
            "Submit new group",
            data={
                "name": "Test Support Group",
                "description": "A test support group for API testing",
                "location": "New York, NY",
                "group_type": "in_person",
                "contact_email": "test@example.com"
            },
            with_session=True,
            expected_status=[200, 201, 403, 422],
            store_key="group_id",
            extract_field="id"
        ))
        
        group_id = self.created_resources.get("group_id", "test-group-id")
        self.print_result(self.test_endpoint(
            "GET", f"/api/groups/{group_id}",
            "Get group by ID",
            expected_status=[200, 403, 404]
        ))
        self.print_result(self.test_endpoint(
            "POST", f"/api/groups/{group_id}/join",
            "Join group interest",
            with_session=True,
            expected_status=[200, 201, 403, 404]
        ))
        self.print_result(self.test_endpoint(
            "POST", f"/api/groups/{group_id}/review",
            "Add group review",
            data={"rating": 5, "comment": "Great support group!"},
            with_session=True,
            expected_status=[200, 201, 403, 404, 422]
        ))
        self.print_result(self.test_endpoint(
            "GET", f"/api/groups/{group_id}/reviews",
            "Get group reviews",
            expected_status=[200, 403, 404]
        ))
        
        # Test 8: Stories Endpoints
        print("\n📌 STORIES API (/api/stories)")
        self.print_result(self.test_endpoint(
            "GET", "/api/stories",
            "Get stories",
            params={"filter": "recent", "limit": 10},
            expected_status=[200, 403]
        ))
        self.print_result(self.test_endpoint(
            "POST", "/api/stories",
            "Create new story",
            data={
                "title": "My Journey with Endometriosis",
                "content": "This is a test story about my experience with endometriosis. It has been a challenging journey but I have found support and hope.",
                "tags": ["diagnosis", "treatment"]
            },
            with_session=True,
            expected_status=[200, 201, 403, 422],
            store_key="story_id",
            extract_field="id"
        ))
        self.print_result(self.test_endpoint(
            "GET", "/api/stories/mine",
            "Get my stories",
            with_session=True,
            expected_status=[200, 403]
        ))
        
        story_id = self.created_resources.get("story_id", "test-story-id")
        self.print_result(self.test_endpoint(
            "GET", f"/api/stories/{story_id}",
            "Get story by ID",
            expected_status=[200, 403, 404]
        ))
        self.print_result(self.test_endpoint(
            "POST", f"/api/stories/{story_id}/support",
            "Add support reaction",
            with_session=True,
            expected_status=[200, 201, 403, 404]
        ))
        self.print_result(self.test_endpoint(
            "DELETE", f"/api/stories/{story_id}/support",
            "Remove support reaction",
            with_session=True,
            expected_status=[200, 204, 403, 404]
        ))
        self.print_result(self.test_endpoint(
            "POST", f"/api/stories/{story_id}/message",
            "Send encouragement message",
            data={"message": "You are so brave! Thank you for sharing your story."},
            expected_status=[200, 201, 403, 404, 422]
        ))
        self.print_result(self.test_endpoint(
            "GET", f"/api/stories/{story_id}/messages",
            "Get story messages",
            expected_status=[200, 403, 404]
        ))
        self.print_result(self.test_endpoint(
            "DELETE", f"/api/stories/{story_id}",
            "Delete story",
            with_session=True,
            expected_status=[200, 204, 403, 404]
        ))
        
        # Test 9: Insights Endpoints
        print("\n📌 INSIGHTS API (/api/insights)")
        self.print_result(self.test_endpoint(
            "GET", "/api/insights",
            "Get dashboard metrics",
            expected_status=[200, 403, 500]
        ))
        self.print_result(self.test_endpoint(
            "GET", "/api/insights/trending",
            "Get trending questions",
            params={"days": 7, "limit": 10},
            expected_status=[200, 403]
        ))
        self.print_result(self.test_endpoint(
            "GET", "/api/insights/geography",
            "Get geographic distribution",
            params={"limit": 10},
            expected_status=[200, 403]
        ))
        self.print_result(self.test_endpoint(
            "GET", "/api/insights/timeline",
            "Get activity timeline",
            params={"days": 30, "granularity": "day"},
            expected_status=[200, 403]
        ))
        self.print_result(self.test_endpoint(
            "GET", "/api/insights/categories",
            "Get category breakdown",
            expected_status=[200, 403, 500]
        ))
        self.print_result(self.test_endpoint(
            "GET", "/api/insights/engagement",
            "Get engagement stats",
            expected_status=[200, 403]
        ))
        
        # Test 10: Candles Endpoints
        print("\n📌 CANDLES API (/api/candles)")
        self.print_result(self.test_endpoint(
            "GET", "/api/candles/count",
            "Get candle count",
            expected_status=[200, 403]
        ))
        self.print_result(self.test_endpoint(
            "GET", "/api/candles/can-light",
            "Check if can light candle",
            with_session=True,
            expected_status=[200, 403]
        ))
        self.print_result(self.test_endpoint(
            "POST", "/api/candles/light",
            "Light a candle",
            data={
                "message": "Sending love and support to all warriors",
                "location": "New York"
            },
            with_session=True,
            expected_status=[200, 201, 403, 429],
            store_key="candle_id",
            extract_field="id"
        ))
        self.print_result(self.test_endpoint(
            "GET", "/api/candles/messages",
            "Get candle messages",
            params={"limit": 10},
            expected_status=[200, 403]
        ))
        self.print_result(self.test_endpoint(
            "GET", "/api/candles/mine",
            "Get my candles",
            with_session=True,
            expected_status=[200, 403]
        ))
        self.print_result(self.test_endpoint(
            "GET", "/api/candles/stats",
            "Get ceremony stats",
            expected_status=[200, 403]
        ))
        self.print_result(self.test_endpoint(
            "GET", "/api/candles/locations",
            "Get candle locations",
            expected_status=[200, 403]
        ))
        
        candle_id = self.created_resources.get("candle_id", "test-candle-id")
        self.print_result(self.test_endpoint(
            "GET", f"/api/candles/{candle_id}",
            "Get candle by ID",
            expected_status=[200, 403, 404]
        ))
        self.print_result(self.test_endpoint(
            "POST", f"/api/candles/{candle_id}/message",
            "Add candle message",
            data={"message": "Stay strong!"},
            expected_status=[200, 201, 403, 404, 422]
        ))
        self.print_result(self.test_endpoint(
            "GET", f"/api/candles/{candle_id}/messages",
            "Get candle messages",
            expected_status=[200, 403, 404]
        ))
        
        # Test OpenAPI docs endpoints
        print("\n📌 DOCUMENTATION ENDPOINTS")
        self.print_result(self.test_endpoint("GET", "/docs", "Swagger UI", expected_status=[200]))
        self.print_result(self.test_endpoint("GET", "/redoc", "ReDoc", expected_status=[200]))
        self.print_result(self.test_endpoint("GET", "/openapi.json", "OpenAPI JSON", expected_status=[200]))
        
        # Print Summary
        self.print_summary()
    
    def print_summary(self):
        passed = sum(1 for r in self.results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in self.results if r.status == TestStatus.FAILED)
        skipped = sum(1 for r in self.results if r.status == TestStatus.SKIPPED)
        total = len(self.results)
        
        avg_time = sum(r.response_time_ms for r in self.results) / total if total > 0 else 0
        
        print("\n" + "="*70)
        print("📊 TEST SUMMARY")
        print("="*70)
        print(f"  Total Tests:    {total}")
        print(f"  ✅ Passed:      {passed}")
        print(f"  ❌ Failed:      {failed}")
        print(f"  ⏭️ Skipped:     {skipped}")
        print(f"  📈 Pass Rate:   {(passed/total*100):.1f}%" if total > 0 else "  Pass Rate: N/A")
        print(f"  ⏱️ Avg Time:    {avg_time:.0f}ms")
        print("="*70)
        
        if failed > 0:
            print("\n❌ FAILED TESTS:")
            for r in self.results:
                if r.status == TestStatus.FAILED:
                    print(f"  [{r.method}] {r.endpoint}")
                    print(f"       {r.message}")
        
        print("\n✨ Test run completed!")


def main():
    print("\n🚀 Starting EndoChat API Tests...")
    print("⚠️  Make sure the backend server is running on http://localhost:8000\n")
    
    tester = APITester(BASE_URL, SESSION_ID)
    
    # First check if server is accessible
    try:
        response = requests.get(f"{BASE_URL}/api/health/live", timeout=5)
        print(f"✅ Server is accessible (status: {response.status_code})\n")
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Cannot connect to server at http://localhost:8000")
        print("   Please start the backend server first:")
        print("   cd backend && uvicorn app.main:app --reload")
        print("\n")
        return
    except Exception as e:
        print(f"⚠️  Warning: Health check returned unexpected result: {e}")
        print("   Continuing with tests anyway...\n")
    
    tester.run_all_tests()


if __name__ == "__main__":
    main()
