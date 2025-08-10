import React, { useEffect, useMemo, useState } from 'react'
import { api } from './api'

// i18n currency formatter (defaults to browser locale)
const nf = new Intl.NumberFormat(navigator.language || 'en-US', { style: 'currency', currency: 'USD' })
const fmt = (n) => nf.format(Number(n||0))

export default function App(){
  // Backend state
  const [prices,setPrices] = useState({})
  const [balances,setBalances] = useState({})
  const [history,setHistory] = useState([])

  // UI state
  const [selected,setSelected] = useState([])
  const [newName,setNewName] = useState('')
  const [newPrice,setNewPrice] = useState('')
  const [tie, setTie] = useState('least_recent') // alpha | least_recent | random | round_robin
  const [toast, setToast] = useState(null)

  // Preview info (from /api/next)
  const [nextInfo, setNextInfo] = useState({ payer:'—', total_cost:0 })

  useEffect(()=>{ refresh() },[])
  async function refresh(){
    const s = await api.state()
    setPrices(s.prices||{})
    setBalances(s.balances||{})
    setHistory(s.history||[])
    setSelected(Object.keys(s.prices||{}))
  }

  const people = useMemo(()=>Object.keys(prices).sort(),[prices])
  const included = useMemo(
      ()=> (selected.length?selected:people).filter(p=>prices.hasOwnProperty(p)),
      [selected,people,prices]
  )

  useEffect(()=>{
    (async ()=>{
      if(included.length === 0){
        setNextInfo({ payer:'—', total_cost:0 })
        return
      }
      const preview = await api.next(included, tie)
      setNextInfo({ payer: preview.payer, total_cost: preview.total_cost })
    })().catch(()=> setNextInfo({ payer:'—', total_cost:0 }))
  }, [included, tie, prices, balances])

  function showToast(msg){ setToast(msg); setTimeout(()=>setToast(null), 1500) }

  async function runRound(){
    const resp = await api.run(included, tie)
    setBalances(resp.balances)
    setHistory(resp.history)
    const preview = await api.next(included, tie).catch(()=>null)
    if(preview) setNextInfo({ payer: preview.payer, total_cost: preview.total_cost })
    showToast('Round recorded')
  }

  async function addOrUpdatePerson(){
    const name = newName.trim()
    const price = newPrice
    if(!name || !price) return
    const resp = await api.setPrice(name, price)
    setPrices(resp.prices); setBalances(resp.balances)
    if(!selected.includes(name)) setSelected(s=>[...s,name])
    setNewName(''); setNewPrice('')
    showToast('Price saved')
  }

  async function removePerson(name){
    if(!confirm(`Remove ${name}? This does not delete history.`)) return
    const resp = await api.removePerson(name)
    setPrices(resp.prices); setBalances(resp.balances)
    setSelected(sel=>sel.filter(p=>p!==name))
    showToast('Removed')
  }

  async function resetBalances(){
    const resp = await api.resetBalances(false)
    setBalances(resp.balances)
    showToast('Balances reset')
  }

  async function clearHistory(){
    if(!confirm('Clear history? This cannot be undone (balances will remain).')) return
    const resp = await api.clearHistory()
    setHistory(resp.history)
    showToast('History cleared')
  }

  function toggleSelected(name){
    setSelected(prev => prev.includes(name) ? prev.filter(p=>p!==name) : [...prev,name])
  }

  return (
      <div style={{backgroundColor:"rgb(255, 251, 242)"}} className="min-h-screen bg-slate-50 text-slate-800 p-9">
        <div className="max-w-7xl mx-auto space-y-6">
          {/* Header */}
          <header className="flex items-center justify-between">
            <h1
                className="text-6xl font-bold"
                style={{ display:'flex', flexDirection:'row', alignItems:'flex-end', gap:'12px' }}
            >
              SplitBucks
              <img src="/favicon.png" alt="SplitBucks Logo" style={{ height: "100px" }} />
            </h1>
            <div className="flex items-center gap-3">
              <button onClick={refresh} style={{backgroundColor:"rgb(150, 121, 105)"}} className="px-3 py-2 rounded-xl bg-slate-900 text-white">Fresh Brew</button>
            </div>
          </header>

          <h2 className="text-4l"> Payment tracker for your Brew-Crew️ 🤟🏼</h2>

          {/* Summary cards */}
          <section className="grid md:grid-cols-3 gap-4">
            <div className="bg-white rounded-2xl shadow p-4">
              <h2 className="font-semibold mb-2">Round roasted by </h2>
              <p className="text-2xl font-bold">{nextInfo.payer}</p>
            </div>
            <div className="bg-white rounded-2xl shadow p-4">
              <h2 className="font-semibold mb-2">Selected total</h2>
              <p className="text-2xl font-bold">{fmt(nextInfo.total_cost)}</p>
            </div>
            <div className="bg-white rounded-2xl shadow p-4">
              <h2 className="font-semibold mb-2">Sipster count</h2>
              <p className="text-2xl font-bold">{people.length}</p>
            </div>
          </section>

          {/* People & Prices */}
          <section className="bg-white rounded-2xl shadow p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-xl">People & Prices</h2>
              <div className="flex gap-4">
                <select className="border rounded px-3 py-2 text-sm" value={tie} onChange={e=>setTie(e.target.value)}>
                  <option value="" disabled>Tie-Breaker</option> {/* Default option */}
                  <option value="least_recent">Least recent</option>
                  <option value="alpha">Alphabetical</option>
                  <option value="round_robin">Round robin</option>
                  <option value="random">Random</option>
                </select>
                <button onClick={resetBalances} style={{ backgroundColor: "rgb(242, 196, 78)"}} className="px-3 py-2 rounded-xl text-white">Clear the Tab</button>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                <tr className="border-b">
                  <th className="py-2">Include</th>
                  <th className="py-2">Name</th>
                  <th className="py-2">Price</th>
                  <th className="py-2">Balance</th>
                  <th className="py-2">Actions</th>
                </tr>
                </thead>
                <tbody>
                {people.map(name => (
                    <tr key={name} className="border-b">
                      <td className="py-2"><input type="checkbox" checked={selected.includes(name)} onChange={()=>toggleSelected(name)} /></td>
                      <td className="py-2 font-medium">{name}</td>
                      <td className="py-2">
                        <input
                            className="border rounded px-2 py-1 w-32"
                            defaultValue={prices[name]}
                            onBlur={async (e)=>{
                              const resp = await api.setPrice(name, e.target.value)
                              setPrices(resp.prices)
                              showToast('Price saved')
                            }}
                        />
                      </td>
                      <td className="py-2">{fmt(balances[name]||0)}</td>
                      <td className="py-2">
                        <button onClick={()=>removePerson(name)} className="px-2 py-1 rounded bg-rose-600 text-white">Remove</button>
                      </td>
                    </tr>
                ))}
                </tbody>
              </table>
            </div>

            {/* Add / Update */}
            <div className="mt-4 flex gap-2 items-end flex-wrap">
              <div>
                <label className="text-sm">Name</label>
                <input value={newName} onChange={e=>setNewName(e.target.value)} className="block border rounded px-3 py-2" placeholder="e.g., Alice" />
              </div>
              <div>
                <label className="text-sm">Price</label>
                <input value={newPrice} onChange={e=>setNewPrice(e.target.value)} className="block border rounded px-3 py-2 w-32" placeholder="e.g., 4.75" />
              </div>
              <button onClick={addOrUpdatePerson} style={{ backgroundColor: "rgb(57, 155, 245)"}} className="px-4 py-2 rounded-xl rgb(228, 181, 91) text-white">Add / Update</button>
            </div>
          </section>

          {/* Run section */}
          <section className="bg-white rounded-2xl shadow p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-xl">Run a Coffee Round</h2>
              <button onClick={runRound} className="px-4 py-2 rounded-xl bg-emerald-600 text-white">Brew the Round</button>
            </div>
            <p className="text-sm text-slate-600 mb-2">
              Every thirsty chugger covers their own brew bill each round, while the noble bean-backer gets crowned with the full coffee bounty 💰
            </p>
          </section>

          {/* History */}
          <section className="bg-white rounded-2xl shadow p-4">
            <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-xl mb-3">History</h2>
            <div className="flex gap-2">
              <button onClick={clearHistory} style={{ backgroundColor: "rgb(242, 196, 78)"}} className="px-3 py-2 rounded-xl text-white">Wipe off the Coffee Rings</button>
            </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                <tr className="border-b">
                  <th className="py-2">Timestamp</th>
                  <th className="py-2">Payer</th>
                  <th className="py-2">Total</th>
                  <th className="py-2">People</th>
                </tr>
                </thead>
                <tbody>
                {history.length===0 && <tr><td className="py-3 text-slate-500" colSpan={4}>No runs yet.</td></tr>}
                {history.map((row, i)=>(
                    <tr key={i} className="border-b">
                      <td className="py-2 whitespace-nowrap" title={row.timestamp}>{new Date(row.timestamp).toLocaleString()}</td>
                      <td className="py-2">{row.payer}</td>
                      <td className="py-2">{fmt(row.total_cost)}</td>
                      <td className="py-2">{(row.people||[]).join(', ')}</td>
                    </tr>
                ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>

        {/* Toast */}
        {toast && (
            <div className="fixed bottom-4 left-1/2 -translate-x-1/2 bg-slate-900 text-white text-sm px-3 py-2 rounded-md shadow">
              {toast}
            </div>
        )}
      </div>
  )
}
