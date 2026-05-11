"""运行所有测试，输出详细报告

用法：
    python tests/run_tests.py           # 运行全部测试
    python tests/run_tests.py -v        # 详细输出
"""

import sys
import os
import time
import unittest
from pathlib import Path

# 将项目根目录加入 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def run_all():
    """发现并运行 tests/ 下所有 test_*.py 文件中的测试"""
    loader = unittest.TestLoader()
    tests_dir = Path(__file__).resolve().parent

    # 使用 discover 自动发现和加载测试
    suite = loader.discover(str(tests_dir), pattern='test_*.py')

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 汇总报告
    total = result.testsRun
    passed = total - len(result.failures) - len(result.errors)
    failed = len(result.failures)
    errors = len(result.errors)

    print()
    print('=' * 55)
    print(f'  测试结果汇总')
    print('=' * 55)
    print(f'  总计: {total}')
    print(f'  通过: {passed}')
    print(f'  失败: {failed}')
    print(f'  错误: {errors}')
    print(f'  成功率: {passed / total * 100:.1f}%' if total else '  无测试')
    print('=' * 55)

    return result.wasSuccessful()


if __name__ == '__main__':
    start = time.time()
    success = run_all()
    elapsed = time.time() - start
    print(f'\n  耗时: {elapsed:.2f} 秒')
    sys.exit(0 if success else 1)
