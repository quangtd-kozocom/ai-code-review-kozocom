"""PHP and Laravel-specific pattern detection.

Provides utilities for detecting Laravel architectural patterns like
Dependency Injection, Facades, Eloquent relationships, etc.
"""

import re
from dataclasses import dataclass
from typing import Literal

import structlog

log = structlog.get_logger()


@dataclass
class PHPUsagePattern:
    """Detected PHP/Laravel usage pattern."""
    
    pattern_type: Literal["di", "facade", "app_helper", "eloquent_relation", "route", "import"]
    class_name: str
    line_number: int
    context: str


class PHPPatternDetector:
    """Detect Laravel-specific usage patterns in PHP code."""
    
    # Laravel Facade mappings (facade name -> service class)
    FACADE_MAPPINGS = {
        "Payment": "PaymentService",
        "Auth": "AuthManager",
        "DB": "DatabaseManager",
        "Cache": "CacheManager",
        "Queue": "QueueManager",
        "Mail": "Mailer",
        "Storage": "FilesystemManager",
        "Log": "LogManager",
    }
    
    def detect_di_usage(self, content: str, class_name: str) -> list[PHPUsagePattern]:
        """Detect Dependency Injection in constructors.
        
        Patterns:
        - __construct(...ClassName $var)
        - __construct(ClassName $var, ...)
        """
        patterns = []
        lines = content.split("\n")
        
        # Pattern: __construct with type-hinted parameter
        di_pattern = rf"__construct\([^)]*{class_name}\s+\$\w+"
        
        for i, line in enumerate(lines, 1):
            if re.search(di_pattern, line):
                patterns.append(PHPUsagePattern(
                    pattern_type="di",
                    class_name=class_name,
                    line_number=i,
                    context=line.strip(),
                ))
        
        return patterns
    
    def detect_facade_usage(self, content: str, class_name: str) -> list[PHPUsagePattern]:
        """Detect Laravel Facade usage.
        
        Patterns:
        - ClassName::method()
        - Payment::process()
        """
        patterns = []
        lines = content.split("\n")
        
        # Check if class_name is a known facade or direct static call
        facade_pattern = rf"{class_name}::\w+\("
        
        for i, line in enumerate(lines, 1):
            if re.search(facade_pattern, line):
                patterns.append(PHPUsagePattern(
                    pattern_type="facade",
                    class_name=class_name,
                    line_number=i,
                    context=line.strip(),
                ))
        
        return patterns
    
    def detect_app_helper_usage(self, content: str, class_name: str) -> list[PHPUsagePattern]:
        """Detect app() helper usage.
        
        Patterns:
        - app(ClassName::class)
        - app('ClassName')
        - resolve(ClassName::class)
        """
        patterns = []
        lines = content.split("\n")
        
        # Pattern: app(ClassName::class) or resolve(ClassName::class)
        app_patterns = [
            rf"app\({class_name}::class\)",
            rf"app\(['\"].*{class_name}['\"]\)",
            rf"resolve\({class_name}::class\)",
        ]
        
        for i, line in enumerate(lines, 1):
            for pattern in app_patterns:
                if re.search(pattern, line):
                    patterns.append(PHPUsagePattern(
                        pattern_type="app_helper",
                        class_name=class_name,
                        line_number=i,
                        context=line.strip(),
                    ))
                    break
        
        return patterns
    
    def detect_eloquent_relations(self, content: str, model_name: str) -> list[PHPUsagePattern]:
        """Detect Eloquent relationship usage.
        
        Patterns:
        - hasMany(ModelName::class)
        - belongsTo(ModelName::class)
        - hasOne, belongsToMany, etc.
        """
        patterns = []
        lines = content.split("\n")
        
        # Eloquent relationship methods
        relation_methods = [
            "hasMany", "hasOne", "belongsTo", "belongsToMany",
            "hasManyThrough", "hasOneThrough", "morphMany", "morphOne",
            "morphTo", "morphToMany",
        ]
        
        for i, line in enumerate(lines, 1):
            for method in relation_methods:
                # Pattern: hasMany(ModelName::class)
                pattern = rf"{method}\({model_name}::class\)"
                if re.search(pattern, line):
                    patterns.append(PHPUsagePattern(
                        pattern_type="eloquent_relation",
                        class_name=model_name,
                        line_number=i,
                        context=line.strip(),
                    ))
                    break
        
        return patterns
    
    def detect_route_usage(self, content: str, controller_name: str) -> list[PHPUsagePattern]:
        """Detect route definitions using controller.
        
        Patterns:
        - Route::get('/path', [ControllerName::class, 'method'])
        - Route::post('/path', 'ControllerName@method')
        """
        patterns = []
        lines = content.split("\n")
        
        # Pattern 1: [ControllerName::class, 'method']
        pattern1 = rf"Route::\w+\([^,]+,\s*\[{controller_name}::class"
        
        # Pattern 2: 'ControllerName@method'
        pattern2 = rf"Route::\w+\([^,]+,\s*['\"].*{controller_name}@"
        
        for i, line in enumerate(lines, 1):
            if re.search(pattern1, line) or re.search(pattern2, line):
                patterns.append(PHPUsagePattern(
                    pattern_type="route",
                    class_name=controller_name,
                    line_number=i,
                    context=line.strip(),
                ))
        
        return patterns
    
    def detect_import_usage(self, content: str, class_name: str) -> list[PHPUsagePattern]:
        """Detect use statement imports.
        
        Patterns:
        - use App\\Services\\ClassName;
        - use ClassName;
        """
        patterns = []
        lines = content.split("\n")
        
        # Pattern: use statement
        import_pattern = rf"use\s+.*{class_name}\s*;"
        
        for i, line in enumerate(lines, 1):
            if re.search(import_pattern, line):
                patterns.append(PHPUsagePattern(
                    pattern_type="import",
                    class_name=class_name,
                    line_number=i,
                    context=line.strip(),
                ))
        
        return patterns
    
    def detect_all_patterns(
        self,
        content: str,
        class_name: str,
    ) -> list[PHPUsagePattern]:
        """Detect all Laravel patterns for a given class.
        
        Args:
            content: PHP file content
            class_name: Class name to search for
            
        Returns:
            List of all detected patterns
        """
        all_patterns = []
        
        all_patterns.extend(self.detect_di_usage(content, class_name))
        all_patterns.extend(self.detect_facade_usage(content, class_name))
        all_patterns.extend(self.detect_app_helper_usage(content, class_name))
        all_patterns.extend(self.detect_eloquent_relations(content, class_name))
        all_patterns.extend(self.detect_route_usage(content, class_name))
        all_patterns.extend(self.detect_import_usage(content, class_name))
        
        log.debug(
            "php_patterns.detected",
            class_name=class_name,
            patterns_found=len(all_patterns),
            types={p.pattern_type for p in all_patterns},
        )
        
        return all_patterns
    
    def resolve_facade_to_class(self, facade_name: str) -> str | None:
        """Resolve a facade name to its underlying service class.
        
        Args:
            facade_name: Facade name (e.g., "Payment")
            
        Returns:
            Service class name or None if not found
        """
        return self.FACADE_MAPPINGS.get(facade_name)
