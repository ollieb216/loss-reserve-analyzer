export const fmt = (n) => {
  if (n === null || n === undefined || isNaN(n)) return '--';
  return Math.round(n).toLocaleString('en-US');
};
