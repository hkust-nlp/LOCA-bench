# MCP Convert

A framework for converting and simplifying MCP (Model Context Protocol) servers to use local file-based databases instead of external APIs.

## 🎯 Purpose

Convert external API-based MCP servers into local, offline versions that:
- **Work without internet connection**
- **Have no rate limits or API costs** 
- **Provide consistent, predictable data** for testing and development
- **Are easy to customize and extend**

## 🏗️ Project Structure

```
mcp-convert/
├── common/                     # Shared utilities and framework
│   ├── database/              # Database handling (JSON, CSV)
│   ├── mcp/                   # MCP server base classes
│   ├── testing/               # Testing framework
│   └── templates/             # Templates for new conversions
├── mcps/                      # Individual MCP implementations
│   ├── yfinance/              # Yahoo Finance MCP
│   └── [future_conversions]/  # Additional MCP servers
├── scripts/                   # Utility scripts
│   ├── create_new_mcp.py      # Generate new MCP from template
│   └── run_all_tests.py       # Test all MCP servers
└── docs/                      # Documentation
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Install with uv (recommended)
uv sync

# Or with pip
pip install -r requirements.txt
```

### 2. Test the YFinance Example

```bash
# Run tests
uv run pytest mcps/yfinance/test_server.py -v

# Start the server
uv run python mcps/yfinance/server.py
```

### 3. Configure Claude Code

Add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "yfinance": {
      "command": "/opt/homebrew/Caskroom/miniforge/base/bin/uv",
      "args": [
        "--directory",
        "/path/to/mcp-convert",
        "run",
        "python",
        "mcps/yfinance/server.py"
      ]
    }
  }
}
```

## 📚 Available MCP Conversions

### YFinance MCP Server

**Status**: ✅ Complete  
**Tools**: 9 tools (stock info, prices, news, financials, options, etc.)  
**Data**: Sample data for AAPL, GOOGL, MSFT, TSLA  

[📖 Documentation](mcps/yfinance/README.md)

## 🛠️ Creating New MCP Conversions

### Using the Generator Script

```bash
# Interactive mode - prompts for configuration
python scripts/create_new_mcp.py --interactive

# Quick example mode
python scripts/create_new_mcp.py
```

### Manual Process

1. **Create directory structure**:
   ```bash
   mkdir -p mcps/your_mcp/{data}
   ```

2. **Copy and customize templates** from `common/templates/`

3. **Add sample data** in the `data/` folder

4. **Implement tools** in `server.py`

5. **Write tests** in `test_server.py`

6. **Update configuration** in `.mcp.json`

## 🧪 Testing

### Test All MCPs

```bash
# Run all tests
python scripts/run_all_tests.py

# Test specific MCP
python scripts/run_all_tests.py -s yfinance

# Verbose output
python scripts/run_all_tests.py -v
```

### Test Individual MCP

```bash
uv run pytest mcps/yfinance/test_server.py -v
```

## 📖 Documentation

- **[Getting Started Guide](docs/GETTING_STARTED.md)** - Step-by-step setup
- **[Conversion Guide](docs/CONVERSION_GUIDE.md)** - How to convert MCPs
- **[Testing Guide](docs/TESTING_GUIDE.md)** - Testing best practices  
- **[API Reference](docs/API_REFERENCE.md)** - Common utilities reference

## 🏗️ Framework Features

### Common Database Layer
- **JsonDatabase** - JSON file operations with querying
- **CsvDatabase** - CSV file operations with pandas integration  
- **BaseDatabase** - Abstract base class for custom databases

### MCP Server Framework
- **BaseMCPServer** - Base class with common MCP functionality
- **ToolRegistry** - Tool management and registration
- **Standard responses** - JSON, text, and error responses

### Testing Framework
- **BaseMCPTest** - Base test class for MCP servers
- **MCPServerTester** - Automated MCP testing utilities
- **DataValidator** - Data integrity validation
- **Mock data generators** - Test data creation utilities

## 🔧 Utility Scripts

### create_new_mcp.py
Generate new MCP conversion from templates

```bash
python scripts/create_new_mcp.py --interactive
```

### run_all_tests.py  
Run tests across all MCP implementations

```bash
python scripts/run_all_tests.py -v
```

## 🎯 Benefits

| Feature | External API | MCP Convert |
|---------|--------------|-------------|
| **Internet Required** | ✅ Yes | ❌ No |
| **Rate Limits** | ⚠️ Usually | ✅ None |
| **API Costs** | 💰 Often | ✅ Free |
| **Response Time** | ⚠️ Variable | ✅ Fast |
| **Data Consistency** | ⚠️ Changes | ✅ Stable |
| **Customization** | ❌ Limited | ✅ Full Control |
| **Testing** | ⚠️ Complex | ✅ Simple |

## 🤝 Contributing

1. **Fork the repository**
2. **Create a new MCP conversion** using the templates
3. **Add comprehensive tests**
4. **Document your implementation**
5. **Submit a pull request**

### Contribution Guidelines

- Follow existing code patterns and structure
- Include comprehensive tests with >90% coverage
- Document all tools and data formats
- Provide sample data for testing
- Update main README with your MCP

## 📁 Example: YFinance Conversion

**Original**: External Yahoo Finance API calls  
**Converted**: Local JSON/CSV files with identical interface

```python
# Same tool interface, different data source
await server.call_tool("get_stock_info", {"ticker": "AAPL"})
```

**Benefits**:
- No Yahoo Finance API key needed
- Works offline
- Predictable test data
- No rate limiting
- Fast responses

## 📄 License

MIT License - Feel free to use and modify for your projects.

## 🔗 Links

- **[Claude Code Documentation](https://docs.anthropic.com/claude/docs)**
- **[MCP Specification](https://spec.modelcontextprotocol.org/)**
- **[Project Issues](https://github.com/your-repo/mcp-convert/issues)**

---

**Made with ❤️ for the MCP community**