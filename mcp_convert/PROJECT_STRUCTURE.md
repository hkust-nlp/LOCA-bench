# MCP Convert - Project Structure

A framework for converting and simplifying MCP (Model Context Protocol) servers to use local file-based databases instead of external APIs.

## New Project Structure

```
mcp-convert/
├── README.md                    # Main project documentation
├── pyproject.toml              # Project configuration
├── requirements.txt            # Python dependencies
├── .mcp.json                   # MCP server configurations
│
├── common/                     # Common utilities and frameworks
│   ├── __init__.py
│   ├── database/               # Database utilities
│   │   ├── __init__.py
│   │   ├── base.py            # Base database interface
│   │   ├── json_db.py         # JSON file database handler
│   │   └── csv_db.py          # CSV file database handler
│   ├── mcp/                   # MCP server utilities
│   │   ├── __init__.py
│   │   ├── server_base.py     # Base MCP server class
│   │   └── tools.py           # Common tool utilities
│   ├── testing/               # Testing framework
│   │   ├── __init__.py
│   │   ├── base_test.py       # Base test classes
│   │   ├── mcp_test.py        # MCP-specific testing utilities
│   │   └── data_validation.py # Data validation utilities
│   └── templates/             # Templates for new conversions
│       ├── mcp_server.py.template
│       ├── database_utils.py.template
│       ├── test_server.py.template
│       └── README.md.template
│
├── mcps/                      # Individual MCP server implementations
│   ├── yfinance/              # Yahoo Finance MCP
│   │   ├── README.md
│   │   ├── server.py          # Main MCP server
│   │   ├── database_utils.py  # Database utilities
│   │   ├── test_server.py     # Tests
│   │   └── data/              # Local data files
│   │       ├── stocks.json
│   │       ├── historical_prices.csv
│   │       └── ...
│   │
│   ├── example_api/           # Example conversion template
│   │   ├── README.md
│   │   ├── server.py
│   │   ├── database_utils.py
│   │   ├── test_server.py
│   │   └── data/
│   │
│   └── [future_mcps]/         # Future MCP conversions
│
├── docs/                      # Documentation
│   ├── GETTING_STARTED.md
│   ├── CONVERSION_GUIDE.md
│   ├── TESTING_GUIDE.md
│   └── API_REFERENCE.md
│
├── scripts/                   # Utility scripts
│   ├── create_new_mcp.py     # Script to scaffold new MCP
│   ├── validate_data.py      # Data validation script
│   └── run_all_tests.py      # Test runner for all MCPs
│
└── tests/                     # Integration tests
    ├── test_common.py         # Test common utilities
    └── test_integration.py    # Cross-MCP integration tests
```

## Key Design Principles

1. **Modular Structure** - Each MCP is self-contained in its own folder
2. **Common Framework** - Shared utilities to reduce duplication
3. **Template-Based** - Easy scaffolding for new MCP conversions
4. **Consistent Testing** - Standardized testing approach across all MCPs
5. **Local Data** - All MCPs use local files instead of external APIs
6. **Easy Configuration** - Simple `.mcp.json` updates for new servers

## Benefits

- **Scalable**: Easy to add new MCP conversions
- **Maintainable**: Common code is centralized
- **Testable**: Consistent testing framework
- **Discoverable**: Clear organization and documentation
- **Reusable**: Templates speed up new conversions