"""
End-to-end tests for HVAC Calculators web application

Tests the integration between the Flask API and the backend calculation logic.
"""

import json
import sys
from app import app


class TestClient:
    """Simple test client for the Flask API."""

    def __init__(self):
        self.app = app
        self.app.config['TESTING'] = True

    def post(self, endpoint, data):
        """Make a POST request to the API."""
        with self.app.test_client() as client:
            response = client.post(
                endpoint,
                data=json.dumps(data),
                content_type='application/json'
            )
            return response.status_code, json.loads(response.get_data(as_text=True))


def run_tests():
    """Run all integration tests."""
    client = TestClient()
    passed = 0
    failed = 0

    print("=" * 60)
    print("HVAC Calculators - End-to-End Integration Tests")
    print("=" * 60)

    # Test 1: Conduit Fill Calculator
    print("\n[Test 1] Conduit Fill Calculator...")
    status, result = client.post('/api/calculate/conduit', {
        'conduit_type': 'EMT',
        'conduit_size': 1.0,
        'wire_gauge': 12,
        'num_wires': 3,
        'insulation_type': 'THHN'
    })

    if status == 200 and result.get('success') and 'fill_percentage' in result.get('data', {}):
        data = result['data']
        print(f"  ✓ Conduit fill: {data['fill_percentage']:.1f}%")
        print(f"  ✓ Status: {data['status']} - {data['status_detail']}")
        passed += 1
    else:
        print(f"  ✗ Failed: {result}")
        failed += 1

    # Test 2: Pipe Sizing Calculator
    print("\n[Test 2] Pipe Sizing Calculator...")
    status, result = client.post('/api/calculate/pipe', {
        'flow_rate_gpm': 50.0,
        'pipe_material': 'CU',
        'max_velocity_fps': 8.0,
        'max_pressure_drop': 4.0
    })

    if status == 200 and result.get('success') and 'recommended_size' in result.get('data', {}):
        data = result['data']
        print(f"  ✓ Recommended size: {data['recommended_size']} inch")
        print(f"  ✓ Velocity: {data['velocity_fps']:.2f} ft/s")
        print(f"  ✓ Status: {data['status']}")
        passed += 1
    else:
        print(f"  ✗ Failed: {result}")
        failed += 1

    # Test 3: Duct Pressure Drop Calculator
    print("\n[Test 3] Duct Pressure Drop Calculator...")
    status, result = client.post('/api/calculate/duct', {
        'airflow_cfm': 1000,
        'duct_width_in': 12,
        'duct_height_in': 12,
        'duct_material': 'galvanized',
        'length_ft': 100
    })

    if status == 200 and result.get('success') and 'equivalent_diameter_in' in result.get('data', {}):
        data = result['data']
        print(f"  ✓ Equivalent diameter: {data['equivalent_diameter_in']:.2f} in")
        print(f"  ✓ Pressure drop: {data['pressure_drop_in_wg']:.3f} in H2O")
        print(f"  ✓ Status: {data['status']}")
        passed += 1
    else:
        print(f"  ✗ Failed: {result}")
        failed += 1

    # Test 4: Fan Laws Calculator (CFM mode)
    print("\n[Test 4] Fan Laws Calculator (CFM)...")
    status, result = client.post('/api/calculate/fan', {
        'cfm_1': 10000,
        'rpm_1': 1200,
        'bhp_1': 10.0,
        'calculation_type': 'cfm',
        'cfm_2': 12000
    })

    if status == 200 and result.get('success') and 'condition_2' in result.get('data', {}):
        data = result['data']['condition_2']
        print(f"  ✓ New RPM: {data['rpm']:.0f}")
        print(f"  ✓ New BHP: {data['bhp']:.2f}")
        passed += 1
    else:
        print(f"  ✗ Failed: {result}")
        failed += 1

    # Test 5: Fan Laws Calculator (RPM mode)
    print("\n[Test 5] Fan Laws Calculator (RPM)...")
    status, result = client.post('/api/calculate/fan', {
        'cfm_1': 10000,
        'rpm_1': 1200,
        'bhp_1': 10.0,
        'calculation_type': 'rpm',
        'rpm_2': 1500
    })

    if status == 200 and result.get('success') and 'condition_2' in result.get('data', {}):
        data = result['data']['condition_2']
        print(f"  ✓ New CFM: {data['cfm']:.0f}")
        print(f"  ✓ New BHP: {data['bhp']:.2f}")
        passed += 1
    else:
        print(f"  ✗ Failed: {result}")
        failed += 1

    # Test 6: Pump Laws Calculator (GPM mode)
    print("\n[Test 6] Pump Laws Calculator (GPM)...")
    status, result = client.post('/api/calculate/pump', {
        'gpm_1': 500,
        'rpm_1': 1750,
        'head_1': 100,
        'bhp_1': 25.0,
        'calculation_type': 'gpm',
        'gpm_2': 600
    })

    if status == 200 and result.get('success') and 'condition_2' in result.get('data', {}):
        data = result['data']['condition_2']
        print(f"  ✓ New RPM: {data['rpm']:.0f}")
        print(f"  ✓ New Head: {data['head_ft']:.1f} ft")
        print(f"  ✓ New BHP: {data['bhp']:.2f}")
        passed += 1
    else:
        print(f"  ✗ Failed: {result}")
        failed += 1

    # Test 7: Pump Laws Calculator (RPM mode)
    print("\n[Test 7] Pump Laws Calculator (RPM)...")
    status, result = client.post('/api/calculate/pump', {
        'gpm_1': 500,
        'rpm_1': 1750,
        'head_1': 100,
        'bhp_1': 25.0,
        'calculation_type': 'rpm',
        'rpm_2': 2100
    })

    if status == 200 and result.get('success') and 'condition_2' in result.get('data', {}):
        data = result['data']['condition_2']
        print(f"  ✓ New GPM: {data['gpm']:.0f}")
        print(f"  ✓ New Head: {data['head_ft']:.1f} ft")
        print(f"  ✓ New BHP: {data['bhp']:.2f}")
        passed += 1
    else:
        print(f"  ✗ Failed: {result}")
        failed += 1

    # Test 8: Validation Error Handling
    print("\n[Test 8] Validation Error Handling...")
    status, result = client.post('/api/calculate/conduit', {
        'conduit_type': 'INVALID',
        'conduit_size': 1.0,
        'wire_gauge': 12,
        'num_wires': 3,
        'insulation_type': 'THHN'
    })

    if status == 400 and not result.get('success'):
        print(f"  ✓ Correctly rejected invalid input")
        print(f"  ✓ Error message: {result.get('error', 'Unknown error')[:50]}...")
        passed += 1
    else:
        print(f"  ✗ Failed to handle validation error properly")
        failed += 1

    # Test 9: Index Page
    print("\n[Test 9] Index Page Loads...")
    with app.test_client() as client_browser:
        response = client_browser.get('/')
        if response.status_code == 200 and b'HVAC Engineering Calculators' in response.get_data():
            print(f"  ✓ Index page loads successfully")
            passed += 1
        else:
            print(f"  ✗ Failed to load index page")
            failed += 1

    # Summary
    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
