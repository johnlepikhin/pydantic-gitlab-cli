"""GitLab CI lint rules."""

from .cache_optimization import (
    GeneralPackageManagerCacheRule,
    GoCacheRule,
    JavaCacheRule,
    NodeCacheRule,
    PythonCacheRule,
    RustCacheRule,
)
from .dependencies import JobDependenciesRule
from .docker import DockerLatestTagRule
from .includes import IncludeVersioningRule
from .naming import JobNamingRule
from .optimization import (
    CachePolicyRule,
    JobReuseRule,
    LintStageRule,
    ParallelizationRule,
    ParallelMatrixLimitRule,
    TimeoutOptimizationRule,
    VariableOptimizationRule,
)
from .quality import (
    ArtifactsExpirationRule,
    CacheRule,
    DockerImageSizeRule,
    InterruptibleFailFastRule,
    KeyOrderRule,
    PackageInstallationRule,
)
from .review import (
    AllowFailureValidityRule,
    ResourceMonitoringRule,
    ReviewAppsRule,
    RulesOptimizationRule,
    StagesCompletenessRule,
)
from .security import CiDebugTraceRule, ProtectedContextRule, SecretsInCodeRule
from .structure import StagesStructureRule
from .syntax import YamlSyntaxRule

__all__ = [
    "AllowFailureValidityRule",
    "ArtifactsExpirationRule",
    "CachePolicyRule",
    "CacheRule",
    "CiDebugTraceRule",
    "DockerImageSizeRule",
    "DockerLatestTagRule",
    "GeneralPackageManagerCacheRule",
    "GoCacheRule",
    "IncludeVersioningRule",
    "InterruptibleFailFastRule",
    "JavaCacheRule",
    "JobDependenciesRule",
    "JobNamingRule",
    "JobReuseRule",
    "KeyOrderRule",
    "LintStageRule",
    "NodeCacheRule",
    "PackageInstallationRule",
    "ParallelMatrixLimitRule",
    "ParallelizationRule",
    "ProtectedContextRule",
    "PythonCacheRule",
    "ResourceMonitoringRule",
    "ReviewAppsRule",
    "RulesOptimizationRule",
    "RustCacheRule",
    "SecretsInCodeRule",
    "StagesCompletenessRule",
    "StagesStructureRule",
    "TimeoutOptimizationRule",
    "VariableOptimizationRule",
    "YamlSyntaxRule",
]
