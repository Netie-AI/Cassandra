/** Shared chrome for docs pages: theme + account (no lang toggle). */
(function () {
  const CC = window.CassandraCommon;
  if (!CC) return;
  CC.initThemeToggle(false);
  CC.initAccountMenu();
})();
