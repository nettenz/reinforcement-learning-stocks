# GPU Acceleration Configuration

## Summary

PyTorch device selection has been updated to automatically detect and use the best available hardware.

## Current Configuration

The code now automatically selects the optimal device:

```python
# Priority order:
1. MPS (Apple Silicon M1/M2/M3/M4 GPU) - if available
2. CUDA (NVIDIA GPU) - if available  
3. CPU (fallback)
```

## Files Updated

- `src/experiments.py` - Device selection for experiment sweeps
- `src/train_bot.py` - Device selection for training scripts

## Important Note: MLP Policies and GPU

**For MLP (Multi-Layer Perceptron) policies like we're using**, Stable Baselines3 documentation indicates that **CPU is often faster than GPU** because:
- MLP networks are relatively small
- GPU overhead (data transfer) can exceed computation savings
- CPU parallelization is efficient for small networks

From SB3 warning:
> "PPO is primarily intended to run on the CPU when not using a CNN policy. 
> The GPU utilization will be poor and training might take longer than on CPU."

## Performance Testing Recommendation

When migrating to SAC with continuous action space, benchmark:
- Training time on CPU vs MPS
- If MPS is slower, we can add a flag to force CPU

## Hardware Detection

Current system:
- Platform: macOS (Apple Silicon)
- GPU: M4 (MPS available)
- PyTorch: 2.11.0 with MPS support

Test MPS acceleration:
```bash
python tests/test_mps_acceleration.py
```

## Future: When CNN Policies Are Used

If we add image-based observations (e.g., candlestick charts, order flow heatmaps):
- GPU acceleration becomes highly beneficial
- MPS/CUDA will provide significant speedup
- The current device selection will automatically utilize GPU

## Current Experiment

The `stability-final-ppo` experiment running now is on CPU (started before this fix).
Future experiments will auto-detect MPS but may still prefer CPU for MLP policies.
