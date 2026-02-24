# Multi-Database Setup Guide

## Overview
This system supports 3 different database engines for 3 tenants:
- **Tenant ITC**: DuckDB (local analytics)
- **Tenant Nestlé**: PostgreSQL (enterprise analytics)
- **Tenant Unilever**: MS SQL Server (cloud-scale analytics)

## Prerequisites

### 1. DuckDB (Already installed)
```bash
pip install duckdb
```

### 2. PostgreSQL
**Install PostgreSQL:**
- Windows: Download from https://www.postgresql.org/download/windows/
- Or use Docker: `docker run --name postgres -e POSTGRES_PASSWORD=mysecretpassword -p 5432:5432 -d postgres`

**Install Python driver:**
```bash
pip install psycopg2-binary
```

### 3. MS SQL Server
**Install SQL Server:**
- Windows: Download SQL Server Express from Microsoft
- Or use Docker: `docker run -e "ACCEPT_EULA=Y" -e "SA_PASSWORD=YourStrong@Passw0rd" -p 1433:1433 -d mcr.microsoft.com/mssql/server:2022-latest`

**Install Python driver:**
```bash
pip install pyodbc
```

**Install ODBC Driver:**
- Download "ODBC Driver 17 for SQL Server" from Microsoft

## Setup Steps

### Step 1: Configure Environment Variables
Create `.env` file in project root:
```bash
# PostgreSQL Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password_here

# MS SQL Server Configuration
MSSQL_SERVER=localhost
MSSQL_PORT=1433
MSSQL_USER=sa
MSSQL_PASSWORD=YourStrong@Passw0rd
```

### Step 2: Create Databases

**PostgreSQL:**
```bash
psql -U postgres
CREATE DATABASE nestle_analytics;
\q

psql -U postgres -d nestle_analytics -f database/schema_postgresql.sql
```

**MS SQL Server:**
```bash
sqlcmd -S localhost -U sa -P YourStrong@Passw0rd
CREATE DATABASE unilever_analytics;
GO
USE unilever_analytics;
GO

# Then run the schema
sqlcmd -S localhost -d unilever_analytics -U sa -P YourStrong@Passw0rd -i database/schema_mssql.sql
```

**DuckDB (ITC):**
```python
python
>>> import duckdb
>>> conn = duckdb.connect('database/itc_olap.duckdb')
>>> conn.execute(open('database/schema.sql').read())
>>> conn.close()
```

### Step 3: Test Connections

```python
from database.multi_db_manager import MultiDatabaseManager

# Initialize manager
db_manager = MultiDatabaseManager('config/database_config.yaml')

# Test each tenant
tenants = db_manager.get_all_tenants()
for tenant_id in tenants:
    try:
        conn = db_manager.get_connection(tenant_id)
        print(f"✅ {tenant_id}: Connected successfully")
    except Exception as e:
        print(f"❌ {tenant_id}: {e}")
```

### Step 4: Load Sample Data

```python
# Generate sample data for each tenant
python database/generate_sample_data.py --tenant tenant_itc
python database/generate_sample_data.py --tenant tenant_nestle
python database/generate_sample_data.py --tenant tenant_unilever
```

## Configuration

### Database Config
Edit `config/database_config.yaml` to customize:
- Connection parameters
- Feature flags per tenant
- Database-specific settings

### Cube.js Multi-Database
Cube.js will automatically route queries to the correct database based on security context (tenant_id).

## Usage

### Python Application
```python
from database.multi_db_manager import execute_tenant_query

# Query tenant-specific database
results = execute_tenant_query(
    tenant_id="tenant_nestle",
    query="SELECT COUNT(*) FROM fact_transactions WHERE date_key > ?",
    params=(20240101,)
)
```

### Cube.js API
```bash
curl -H "Authorization: Bearer TOKEN" \
     -H "X-Tenant-ID: tenant_nestle" \
     http://localhost:4000/cubejs-api/v1/load?query=...
```

## Troubleshooting

### PostgreSQL Connection Issues
- Check if PostgreSQL service is running
- Verify firewall allows port 5432
- Check pg_hba.conf for authentication settings

### MS SQL Server Connection Issues
- Verify SQL Server is running
- Enable TCP/IP in SQL Server Configuration Manager
- Check Windows Firewall allows port 1433
- Verify ODBC Driver is installed

### DuckDB Issues
- Ensure database file path is correct
- Check file permissions
- Verify disk space available

## Performance Tuning

### PostgreSQL
```sql
-- Increase shared buffers
ALTER SYSTEM SET shared_buffers = '2GB';
-- Increase work_mem
ALTER SYSTEM SET work_mem = '50MB';
```

### MS SQL Server
```sql
-- Set max server memory
EXEC sp_configure 'max server memory (MB)', 4096;
RECONFIGURE;
```

### DuckDB
```python
conn.execute("SET memory_limit='4GB'")
conn.execute("SET threads=8")
```

## Security

- Never commit `.env` file (already in .gitignore)
- Use strong passwords for database accounts
- Enable SSL/TLS for PostgreSQL and MS SQL Server in production
- Implement proper user authentication and authorization
- Regular security audits and updates

## Monitoring

### Connection Pool Status
```python
manager = MultiDatabaseManager()
for tenant_id in manager.get_all_tenants():
    config = manager.get_tenant_config(tenant_id)
    print(f"{tenant_id} ({config.db_type}): {config.tenant_name}")
```

### Query Performance
- Enable query logging in each database
- Use EXPLAIN ANALYZE for slow queries
- Monitor connection pool utilization

## Backup & Recovery

### PostgreSQL
```bash
pg_dump -U postgres nestle_analytics > backup_nestle.sql
```

### MS SQL Server
```sql
BACKUP DATABASE unilever_analytics TO DISK = 'D:\backups\unilever.bak';
```

### DuckDB
```bash
cp database/itc_olap.duckdb database/backups/itc_olap_backup.duckdb
```

## Next Steps

1. ✅ Set up all 3 databases
2. ✅ Test connections
3. ⏳ Load sample data
4. ⏳ Configure Cube.js schemas for each database
5. ⏳ Test multi-tenant queries
6. ⏳ Deploy to production
