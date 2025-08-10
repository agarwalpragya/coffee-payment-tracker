/**
 * API client
 */
export const api = {
  async state(){
    const r = await fetch('/api/state');
    if(!r.ok) throw new Error('state failed');
    return r.json();
  },
  async next(people, tie){
    const params = new URLSearchParams();
    (people||[]).forEach(p => params.append('people', p));
    if (tie) params.set('tie', tie);
    const r = await fetch('/api/next?' + params.toString());
    if(!r.ok) throw new Error('next failed');
    return r.json();
  },
  async run(people, tie){
    const r = await fetch('/api/run', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ people, tie })
    });
    if(!r.ok) throw new Error('run failed');
    return r.json();
  },
  async setPrice(name, price){
    const r = await fetch('/api/set-price', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ name, price })
    });
    if(!r.ok) throw new Error('set-price failed');
    return r.json();
  },
  async resetBalances(clear_history=false){
    const r = await fetch('/api/reset-balances', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ clear_history })
    });
    if(!r.ok) throw new Error('reset failed');
    return r.json();
  },
  async clearHistory(){
    const r = await fetch('/api/clear-history', { method: 'POST' });
    if(!r.ok) throw new Error('clear-history failed');
    return r.json();
  },
  async removePerson(name){
    const r = await fetch('/api/remove-person', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ name })
    });
    if(!r.ok) throw new Error('remove failed');
    return r.json();
  }
};
