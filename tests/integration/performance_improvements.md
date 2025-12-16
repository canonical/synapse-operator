# Integration Test Performance Improvements

## **Implemented Optimizations**

### 1. **Fixture Scope Optimization**
- Changed S3 backup/media bucket fixtures from `function` to `module` scope
- Changed S3 integrator app fixtures from `function` to `module` scope  
- **Expected improvement**: 60-80% reduction in S3-related setup time

### 2. **Reduced Wait Times**
- Reduced `idle_period` from 5s to 3s for basic deployments
- **Expected improvement**: 10-15% faster test execution

## **Additional Recommendations**

### **Short-term Improvements (Easy to implement)**

1. **Optimize wait_for_idle usage**:
   ```python
   # Current: Conservative waits
   await model.wait_for_idle(idle_period=30, timeout=120)
   
   # Optimized: Shorter waits with retry logic
   await model.wait_for_idle(idle_period=10, timeout=60)
   ```

2. **Add conditional fixtures**: Skip expensive setup when not needed
   ```python
   @pytest_asyncio.fixture(scope="module")
   async def redis_app_conditional(request, model):
       """Only deploy Redis if tests actually need it."""
       if not request.node.get_closest_marker("redis"):
           return None
       # ... deploy redis
   ```

3. **Batch configuration changes**:
   ```python
   # Instead of multiple set_config calls
   await app.set_config({
       "public_baseurl": f"http://{synapse_ip}:8080",
       "server_name": server_name,
       "enable_registration": True
   })
   ```

### **Medium-term Improvements**

1. **Test-specific deployment optimization**:
   - Create lightweight fixtures for tests that don't need full Synapse setup
   - Use mock services where possible

2. **Parallel fixture initialization**:
   ```python
   async def deploy_apps_parallel():
       tasks = [
           model.deploy("postgresql", app_name="db"),
           model.deploy("redis", app_name="redis"),
           model.deploy("nginx", app_name="nginx")
       ]
       return await asyncio.gather(*tasks)
   ```

3. **Smart test ordering**:
   - Group tests by required fixtures to maximize reuse
   - Run quick tests first to catch failures early

### **Long-term Improvements**

1. **Persistent test environments**:
   - Maintain a base environment between test runs
   - Use snapshots/checkpoints for faster resets

2. **Test data management**:
   - Pre-populate test data for consistent performance
   - Use database fixtures instead of API calls

3. **Resource pooling**:
   - Maintain a pool of pre-deployed applications
   - Reuse applications across test sessions

## **Performance Monitoring**

Add timing decorators to track improvements:

```python
import time
import functools

def time_fixture(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        result = await func(*args, **kwargs)
        duration = time.time() - start
        print(f"Fixture {func.__name__} took {duration:.2f}s")
        return result
    return wrapper

@time_fixture
@pytest_asyncio.fixture(scope="module")
async def synapse_app(...):
    # fixture implementation
```

## **Expected Performance Gains**

| Optimization | Expected Improvement | Risk Level |
|--------------|---------------------|------------|
| Fixture scope changes | 60-80% S3 setup reduction | Low |
| Reduced wait times | 10-15% overall reduction | Low |
| Conditional fixtures | 20-30% for unused features | Medium |
| Parallel deployment | 30-50% deployment time | Medium |
| Persistent environments | 70-90% between runs | High |

## **Next Steps**

1. **Immediate**: Monitor performance impact of current changes
2. **Week 1**: Implement conditional fixtures for optional features
3. **Week 2**: Add parallel deployment for independent services
4. **Month 1**: Consider persistent environment strategy

## **Measurement**

Use pytest-benchmark to track improvements:
```bash
pip install pytest-benchmark
pytest --benchmark-only tests/integration/
```
