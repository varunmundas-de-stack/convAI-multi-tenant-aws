// DimSalesHierarchy — sales force hierarchy (SO → ASM → ZSM → NSM)
// Used by queryRewrite for row-level security filtering

const clientId = COMPILE_CONTEXT.securityContext && COMPILE_CONTEXT.securityContext.clientId
  ? COMPILE_CONTEXT.securityContext.clientId
  : 'nestle';

const schema = `client_${clientId}`;

cube('DimSalesHierarchy', {
  sql: `SELECT * FROM ${schema}.dim_sales_hierarchy`,

  measures: {
    count: {
      type: `count`,
      drillMembers: [hierarchy_key, so_name],
    },
  },

  dimensions: {
    hierarchy_key: {
      sql: `hierarchy_key`,
      type: `number`,
      primaryKey: true,
    },

    // Sales Officer level
    so_code: {
      sql: `so_code`,
      type: `string`,
      title: `SO Code`,
    },

    so_name: {
      sql: `so_name`,
      type: `string`,
      title: `SO Name`,
    },

    // Area Sales Manager level
    asm_code: {
      sql: `asm_code`,
      type: `string`,
      title: `ASM Code`,
    },

    asm_name: {
      sql: `asm_name`,
      type: `string`,
      title: `ASM Name`,
    },

    // Zonal Sales Manager level
    zsm_code: {
      sql: `zsm_code`,
      type: `string`,
      title: `ZSM Code`,
    },

    zsm_name: {
      sql: `zsm_name`,
      type: `string`,
      title: `ZSM Name`,
    },

    // National Sales Manager level
    nsm_code: {
      sql: `nsm_code`,
      type: `string`,
      title: `NSM Code`,
    },

    nsm_name: {
      sql: `nsm_name`,
      type: `string`,
      title: `NSM Name`,
    },

    // Geographic hierarchy (stored in sales hierarchy, not dim_geography)
    zone_name: {
      sql: `zone_name`,
      type: `string`,
      title: `Zone`,
    },

    region_name: {
      sql: `region_name`,
      type: `string`,
      title: `Region`,
    },
  },
});
