// DimGeography — geographic hierarchy dimension

const clientId = COMPILE_CONTEXT.securityContext && COMPILE_CONTEXT.securityContext.clientId
  ? COMPILE_CONTEXT.securityContext.clientId
  : 'nestle';

const schema = `client_${clientId}`;

cube('DimGeography', {
  sql: `SELECT * FROM ${schema}.dim_geography`,

  measures: {
    count: {
      type: `count`,
      drillMembers: [geography_key, state_name],
    },
  },

  dimensions: {
    geography_key: {
      sql: `geography_key`,
      type: `number`,
      primaryKey: true,
    },

    state_name: {
      sql: `state_name`,
      type: `string`,
      title: `State`,
    },

    district_name: {
      sql: `district_name`,
      type: `string`,
      title: `District`,
    },

    town_name: {
      sql: `town_name`,
      type: `string`,
      title: `Town`,
    },

  },
});
