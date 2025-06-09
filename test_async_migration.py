#!/usr/bin/env python3
"""
Test script to verify the async migration works correctly
"""

import asyncio
import json
import sys
from datetime import datetime

# Test the async queue
async def test_async_queue():
    print("Testing AsyncQueue...")
    
    try:
        from app.queue.queue import AsyncQueue
        
        # Create a test queue
        queue = AsyncQueue(check_update=False)
        
        # Test putting items
        await queue.put(datetime.utcnow(), 'test_type', 'test_uuid', 'test_id', {'test': 'data'})
        print("✓ Queue put operation works")
        
        # Test getting items
        type_, uuid_, identifier, data = await queue.get_next_ready_item()
        if type_ == 'test_type':
            print("✓ Queue get operation works")
        else:
            print("✗ Queue get operation failed")
            
        # Test serialization
        serialized = await queue.serialize()
        print(f"✓ Queue serialization works: {len(serialized)} items")
        
    except Exception as e:
        print(f"✗ AsyncQueue test failed: {e}")
        return False
    
    return True


async def test_async_websocket():
    print("Testing AsyncWebSocket...")
    
    try:
        from app.ui.websocket import AsyncIncidentWS
        
        # Create websocket manager
        ws_manager = AsyncIncidentWS()
        print("✓ AsyncWebSocket creation works")
        
        # Test broadcast (should not fail even with no connections)
        await ws_manager.broadcast('test_event', {'test': 'data'})
        print("✓ AsyncWebSocket broadcast works")
        
    except Exception as e:
        print(f"✗ AsyncWebSocket test failed: {e}")
        return False
    
    return True


async def test_async_handlers():
    print("Testing async handlers...")
    
    try:
        # Test that handlers can be imported
        from app.queue.handlers.base_handler import BaseHandler
        from app.queue.handlers.alert_handler import AlertHandler
        from app.queue.handlers.status_update_handler import StatusUpdateHandler
        from app.queue.handlers.step_handler import StepHandler
        from app.queue.handlers.update_handler import UpdateHandler
        
        print("✓ All async handlers import successfully")
        
        # Check that handle methods are async
        import inspect
        
        # Create dummy instances for testing (this won't work fully without real dependencies)
        # But we can at least check the method signatures
        
        handlers = [AlertHandler, StatusUpdateHandler, StepHandler, UpdateHandler]
        for handler_class in handlers:
            handle_method = getattr(handler_class, 'handle')
            if inspect.iscoroutinefunction(handle_method):
                print(f"✓ {handler_class.__name__}.handle is async")
            else:
                print(f"✗ {handler_class.__name__}.handle is not async")
                return False
                
    except Exception as e:
        print(f"✗ Async handlers test failed: {e}")
        return False
    
    return True


async def test_fastapi_import():
    print("Testing FastAPI application import...")
    
    try:
        # Test that the main async app can be imported
        import main
        
        if hasattr(main, 'app'):
            print("✓ FastAPI app imports successfully")
        else:
            print("✗ FastAPI app not found in main")
            return False
            
    except Exception as e:
        print(f"✗ FastAPI import test failed: {e}")
        return False
    
    return True


async def main():
    print("🚀 Testing async migration...")
    print("=" * 50)
    
    tests = [
        test_async_queue,
        test_async_websocket,
        test_async_handlers,
        test_fastapi_import
    ]
    
    results = []
    for test in tests:
        try:
            result = await test()
            results.append(result)
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
            results.append(False)
        print()
    
    print("=" * 50)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"🎉 All tests passed! ({passed}/{total})")
        print("✅ Async migration appears to be working correctly")
        return 0
    else:
        print(f"❌ Some tests failed ({passed}/{total})")
        print("⚠️  Please check the errors above")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main())) 