
import React, { useEffect, useMemo, useState } from 'react'
import { api } from './api'

function toFixed2(n){return Number(n||0).toFixed(2)}

export default function App(){
  const [prices,setPrices] = useState({})
  const [balances,setBalances] = useState({})
  const [history,setHistory] = useState([])
  const [selected,setSelected] = useState([])
  const [newName,setNewName] = useState('')
  const [newPrice,setNewPrice] = useState('')

  useEffect(()=>{ refresh() },[])
  async function refresh(){
    const s = await api.state()
    setPrices(s.prices||{}); setBalances(s.balances||{}); setHistory(s.history||[])
    setSelected(Object.keys(s.prices||{}))
  }

  const people = useMemo(()=>Object.keys(prices).sort(),[prices])
  const included = useMemo(()=> (selected.length?selected:people).filter(p=>prices.hasOwnProperty(p)), [selected,people,prices])
  const totalSelected = useMemo(()=> included.reduce((a,p)=>a+Number(prices[p]||0),0), [included,prices])

  const nextPayer = useMemo(()=>{
    if(!included.length) return '—'
    const present = included.filter(c=>balances.hasOwnProperty(c))
    if(!present.length) return '—'
    const minVal = Math.min(...present.map(p=>balances[p]))
    return present.filter(p=>balances[p]===minVal).sort()[0] || '—'
  },[included,balances])

  async function runRound(){
    const resp = await api.run(included)
    setBalances(resp.balances); setHistory(resp.history)
  }

  async function addOrUpdatePerson(){
    const name = newName.trim(); const price = parseFloat(newPrice)
    if(!name || isNaN(price) || price<=0) return
    const resp = await api.setPrice(name, price)
    setPrices(resp.prices); setBalances(resp.balances)
    if(!selected.includes(name)) setSelected(s=>[...s,name])
    setNewName(''); setNewPrice('')
  }

  async function removePerson(name){
    const resp = await api.removePerson(name)
    setPrices(resp.prices); setBalances(resp.balances)
    setSelected(sel=>sel.filter(p=>p!==name))
  }

  async function resetBalances(){
    const resp = await api.resetBalances()
    setBalances(resp.balances)
  }

  function toggleSelected(name){
    setSelected(prev => prev.includes(name) ? prev.filter(p=>p!==name) : [...prev,name])
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 p-20">
      <div className="max-w-6xl mx-auto space-y-6">
        <header className="flex items-center justify-between">
          <h1 className="text-5xl font-bold"> SplitBucks ☕️</h1>
          <button onClick={refresh} className="px-3 py-2 rounded-xl bg-slate-900 text-white">Refresh</button>
        </header>

        <h2 className="text-4l"> Payment tracker for your Brew-Crew️ 🤟🏼</h2>

        <section className="grid md:grid-cols-3 gap-4">
          <div className="bg-white rounded-2xl shadow p-4">
            <h2 className="font-semibold mb-2">Next payer</h2>
            <p className="text-2xl font-bold">{nextPayer}</p>
          </div>
          <div className="bg-white rounded-2xl shadow p-4">
            <h2 className="font-semibold mb-2">Selected total</h2>
            <p className="text-2xl font-bold">${toFixed2(totalSelected)}</p>
          </div>
          <div className="bg-white rounded-2xl shadow p-4">
            <h2 className="font-semibold mb-2">People count</h2>
            <p className="text-2xl font-bold">{people.length}</p>
          </div>
        </section>

        <section className="bg-white rounded-2xl shadow p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-xl">People & Prices</h2>
            <button onClick={resetBalances} className="px-3 py-2 rounded-xl bg-amber-500 text-white">Reset Balances</button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b">
                  <th className="py-2">Include</th>
                  <th className="py-2">Name</th>
                  <th className="py-2">Price ($)</th>
                  <th className="py-2">Balance ($)</th>
                  <th className="py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {people.map(name => (
                  <tr key={name} className="border-b">
                    <td className="py-2"><input type="checkbox" checked={selected.includes(name)} onChange={()=>toggleSelected(name)} /></td>
                    <td className="py-2 font-medium">{name}</td>
                    <td className="py-2">
                      <input className="border rounded px-2 py-1 w-28" defaultValue={prices[name]} onBlur={async (e)=>{ const v=parseFloat(e.target.value); if(!isNaN(v) && v>0){ const resp=await api.setPrice(name,v); setPrices(resp.prices) } }} />
                    </td>
                    <td className="py-2">{toFixed2(balances[name]||0)}</td>
                    <td className="py-2"><button onClick={()=>removePerson(name)} className="px-2 py-1 rounded bg-rose-600 text-white">Remove</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-4 flex gap-2 items-end flex-wrap">
            <div>
              <label className="text-sm">Name</label>
              <input value={newName} onChange={e=>setNewName(e.target.value)} className="block border rounded px-3 py-2" placeholder="e.g., Alice" />
            </div>
            <div>
              <label className="text-sm">Price ($)</label>
              <input value={newPrice} onChange={e=>setNewPrice(e.target.value)} className="block border rounded px-3 py-2" placeholder="e.g., 4.75" />
            </div>
            <button onClick={addOrUpdatePerson} className="px-4 py-2 rounded-xl bg-emerald-600 text-white">Add / Update</button>
          </div>
        </section>

        <section className="bg-white rounded-2xl shadow p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-xl">Run a Coffee Round</h2>
            <button onClick={runRound} className="px-4 py-2 rounded-xl bg-slate-900 text-white">Run</button>
          </div>
          <p className="text-sm text-slate-600 mb-2">Lowest cumulative spender pays. Total = sum of selected drink prices.</p>
        </section>

        <section className="bg-white rounded-2xl shadow p-4">
          <h2 className="font-semibold text-xl mb-3">History</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b">
                  <th className="py-2">Timestamp</th>
                  <th className="py-2">Payer</th>
                  <th className="py-2">Total ($)</th>
                  <th className="py-2">People</th>
                </tr>
              </thead>
              <tbody>
                {history.length===0 && <tr><td className="py-3 text-slate-500" colSpan={4}>No runs yet.</td></tr>}
                {history.map((row, i)=>(
                  <tr key={i} className="border-b">
                    <td className="py-2 whitespace-nowrap">{new Date(row.timestamp).toLocaleString()}</td>
                    <td className="py-2">{row.payer}</td>
                    <td className="py-2">{toFixed2(row.total_cost)}</td>
                    <td className="py-2">{(row.people||[]).join(', ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <footer className="text-sm text-slate-500 pb-6">
          Flask API + React/Tailwind. Algorithm: pick lowest cumulative spender; add round total to their balance; log history.
        </footer>
      </div>
    </div>
  )
}
