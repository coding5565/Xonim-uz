<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Banknote, CalendarCheck, Download, Pencil, Plus, Search, ShieldCheck, UserRoundCog, Users } from '@lucide/vue'
import { api, download, money, today } from '../api'
import AppModal from '../components/AppModal.vue'

interface Staff {
  id: number; name: string; username: string; role: 'owner'|'admin'|'cashier'|'kitchen'; active: boolean
  phone: string; salary: string; hired_at: string|null; notes: string; last_login: string|null
  last_salary_period: string|null; last_salary_paid_on: string|null
}
interface SalaryPayment { id:number; period:string; amount:string; payment_method:'cash'|'card'; paid_on:string; note:string; actor_name:string }

const staff=ref<Staff[]>([]), payments=ref<SalaryPayment[]>([]), selected=ref<Staff>(), query=ref('')
const createOpen=ref(false), editOpen=ref(false), payOpen=ref(false), historyOpen=ref(false)
const busy=ref(false), error=ref(''), formError=ref('')
const currentMonth=today().slice(0,7)
const createForm=reactive({name:'',username:'',role:'admin',password:'',phone:'',salary:'',hired_at:today(),notes:''})
const editForm=reactive({name:'',role:'admin',phone:'',salary:'',hired_at:'',notes:'',active:true})
const payForm=reactive({period:currentMonth,amount:'',payment_method:'cash',paid_on:today(),note:''})
const filtered=computed(()=>staff.value.filter(item=>`${item.name} ${item.username} ${item.phone} ${item.role}`.toLocaleLowerCase().includes(query.value.toLocaleLowerCase())))
const employees=computed(()=>staff.value.filter(item=>item.role!=='owner'))
const activeCount=computed(()=>employees.value.filter(item=>item.active).length)
const monthlyPayroll=computed(()=>employees.value.filter(item=>item.active).reduce((sum,item)=>sum+Number(item.salary),0))
const paidThisMonth=computed(()=>employees.value.filter(item=>item.last_salary_period===currentMonth).length)

async function load(){try{staff.value=await api<Staff[]>('staff/')}catch(e){error.value=(e as Error).message}}
onMounted(load)
function startCreate(){Object.assign(createForm,{name:'',username:'',role:'admin',password:'',phone:'',salary:'',hired_at:today(),notes:''});formError.value='';createOpen.value=true}
async function createStaff(){busy.value=true;formError.value='';try{await api('staff/',{method:'POST',body:JSON.stringify({...createForm,salary:createForm.salary||'0',hired_at:createForm.hired_at||null})});createOpen.value=false;await load()}catch(e){formError.value=(e as Error).message}finally{busy.value=false}}
function startEdit(item:Staff){selected.value=item;Object.assign(editForm,{name:item.name,role:item.role,phone:item.phone,salary:item.salary,hired_at:item.hired_at||'',notes:item.notes,active:item.active});formError.value='';editOpen.value=true}
async function updateStaff(){if(!selected.value)return;busy.value=true;formError.value='';try{await api(`staff/${selected.value.id}/`,{method:'PATCH',body:JSON.stringify({...editForm,hired_at:editForm.hired_at||null})});editOpen.value=false;await load()}catch(e){formError.value=(e as Error).message}finally{busy.value=false}}
async function loadPayments(item:Staff){payments.value=await api<SalaryPayment[]>(`staff/${item.id}/salary-payments/`)}
async function startPay(item:Staff){selected.value=item;Object.assign(payForm,{period:currentMonth,amount:item.salary,payment_method:'cash',paid_on:today(),note:''});formError.value='';try{await loadPayments(item);payOpen.value=true}catch(e){error.value=(e as Error).message}}
async function paySalary(){if(!selected.value)return;busy.value=true;formError.value='';try{await api(`staff/${selected.value.id}/salary-payments/`,{method:'POST',body:JSON.stringify(payForm)});payOpen.value=false;await load()}catch(e){formError.value=(e as Error).message}finally{busy.value=false}}
async function showHistory(item:Staff){selected.value=item;error.value='';try{await loadPayments(item);historyOpen.value=true}catch(e){error.value=(e as Error).message}}
const roleName=(role:string)=>role==='owner'?'Superadmin':role==='admin'?'Admin':role==='kitchen'?'Oshxona':'Kassir'
async function exportPayroll(){try{await download('staff/salary-payments/export/','honim-umumiy-oyliklar.xlsx')}catch(e){error.value=(e as Error).message}}
</script>

<template>
  <div class="page-heading"><div><span class="eyebrow">JAMOA VA ISH HAQI</span><h1>Xodimlar<span class="heading-dot">.</span></h1><p>Hisoblar, lavozimlar va oylik to‘lovlari bir joyda.</p></div><div class="heading-actions"><button class="button secondary" @click="exportPayroll"><Download :size="17"/>Oyliklar Excel</button><button class="button primary" @click="startCreate"><Plus :size="18"/>Xodim yaratish</button></div></div>
  <p v-if="error" class="alert error">{{ error }}</p>
  <div class="staff-summary-grid">
    <article><Users/><span>Faol xodimlar</span><strong>{{ activeCount }}</strong><small>{{ employees.length }} ta xodim hisobidan</small></article>
    <article><Banknote/><span>Oylik ish haqi fondi</span><strong>{{ money(monthlyPayroll) }}</strong><small>so‘m / oy</small></article>
    <article><CalendarCheck/><span>{{ currentMonth }} da to‘langan</span><strong>{{ paidThisMonth }} / {{ activeCount }}</strong><small>har xodimga oyiga bir marta</small></article>
  </div>
  <section class="panel"><header class="panel-heading"><div><h2>Xodimlar ro‘yxati</h2><p>Rol, oylik va hisob holatini boshqaring</p></div><div class="search-field"><Search :size="17"/><input v-model="query" placeholder="Ism, login yoki telefon…" aria-label="Xodim qidirish"></div></header><div class="table-wrap"><table><thead><tr><th>XODIM</th><th>ROL</th><th>OYLIK</th><th>SO‘NGGI TO‘LOV</th><th>HOLAT</th><th>AMALLAR</th></tr></thead><tbody>
    <tr v-for="item in filtered" :key="item.id"><td><strong>{{ item.name }}</strong><small>@{{ item.username }}{{ item.phone?` · ${item.phone}`:'' }}</small></td><td><span class="pill subtle">{{ roleName(item.role) }}</span></td><td class="number">{{ item.role==='owner'?'—':`${money(item.salary)} so‘m` }}</td><td><span v-if="item.role==='owner'">—</span><template v-else-if="item.last_salary_period"><strong>{{ item.last_salary_period }}</strong><small>{{ item.last_salary_paid_on }}</small></template><span v-else>To‘lov yo‘q</span></td><td><span class="status" :class="item.active?'paid':'open'">{{ item.active?'Faol':'Bloklangan' }}</span></td><td><div v-if="item.role!=='owner'" class="staff-actions"><button class="table-action" title="Tahrirlash" @click="startEdit(item)"><Pencil :size="15"/></button><button class="table-action pay" @click="startPay(item)"><Banknote :size="15"/>Oylik</button><button class="text-link" @click="showHistory(item)">Tarix</button></div><small v-else>Bosh hisob</small></td></tr>
  </tbody></table><div v-if="!filtered.length" class="empty-state"><UserRoundCog :size="38" :stroke-width="1.3"/><h3>Xodim topilmadi</h3></div></div></section>
  <div class="inline-tip"><ShieldCheck :size="20"/><span>Oylik to‘lovi saqlanganda “Ish haqi” kategoriyasida xarajat yaratiladi va superadmin dashboardida darhol hisoblanadi.</span></div>

  <AppModal :open="createOpen" title="Yangi xodim hisobi" @close="!busy&&(createOpen=false)"><form @submit.prevent="createStaff">
    <div class="form-row"><label>Xodim ismi<input v-model="createForm.name" required maxlength="150" placeholder="Masalan, Azizbek"></label><label>Telefon<input v-model="createForm.phone" maxlength="30" placeholder="+998 90 123 45 67"></label></div>
    <div class="form-row"><label>Login<input v-model="createForm.username" required minlength="3" maxlength="150" pattern="[A-Za-z0-9_@.+-]+" autocomplete="off" placeholder="aziz_admin"></label><label>Rol<select v-model="createForm.role"><option value="admin">Admin</option><option value="cashier">Kassir</option><option value="kitchen">Oshxona</option></select></label></div>
    <div class="form-row"><label>Oylik, so‘m<input v-model="createForm.salary" type="number" min="0" step="1000" placeholder="3500000"></label><label>Ishga kirgan sana<input v-model="createForm.hired_at" type="date" :max="today()"></label></div>
    <label>Vaqtinchalik parol<input v-model="createForm.password" type="password" required minlength="12" maxlength="128" autocomplete="new-password" placeholder="Kamida 12 belgi"></label><label>Izoh<textarea v-model="createForm.notes" maxlength="300" rows="2" placeholder="Lavozim yoki qo‘shimcha ma’lumot"/></label>
    <p class="alert">Login va parolni xodimga xavfsiz yetkazing. Tizim parolni keyin qayta ko‘rsatmaydi.</p><p v-if="formError" class="alert error">{{ formError }}</p><button class="button primary full" :disabled="busy">{{ busy?'Yaratilmoqda…':'Hisobni yaratish' }}</button>
  </form></AppModal>

  <AppModal :open="editOpen" title="Xodim ma’lumotlari" @close="!busy&&(editOpen=false)"><form @submit.prevent="updateStaff">
    <div class="form-row"><label>Ism<input v-model="editForm.name" required maxlength="150"></label><label>Telefon<input v-model="editForm.phone" maxlength="30"></label></div><div class="form-row"><label>Rol<select v-model="editForm.role"><option value="admin">Admin</option><option value="cashier">Kassir</option><option value="kitchen">Oshxona</option></select></label><label>Oylik, so‘m<input v-model="editForm.salary" type="number" min="0" step="1000" required></label></div>
    <label>Ishga kirgan sana<input v-model="editForm.hired_at" type="date" :max="today()"></label><label>Izoh<textarea v-model="editForm.notes" maxlength="300" rows="2"/></label><label class="checkbox"><input v-model="editForm.active" type="checkbox">Hisob faol, tizimga kira oladi</label>
    <p v-if="formError" class="alert error">{{ formError }}</p><button class="button primary full" :disabled="busy">{{ busy?'Saqlanmoqda…':'O‘zgarishlarni saqlash' }}</button>
  </form></AppModal>

  <AppModal :open="payOpen" :title="`${selected?.name||''} · oylik to‘lovi`" @close="!busy&&(payOpen=false)"><form @submit.prevent="paySalary">
    <div class="salary-amount">{{ money(payForm.amount||0) }} <small>so‘m</small></div><div class="form-row"><label>Qaysi oy uchun?<input v-model="payForm.period" type="month" :max="currentMonth" required></label><label>To‘lov sanasi<input v-model="payForm.paid_on" type="date" :max="today()" required></label></div><div class="form-row"><label>Summa<input v-model="payForm.amount" type="number" min="1" step="1000" required></label><label>To‘lov usuli<select v-model="payForm.payment_method"><option value="cash">Naqd</option><option value="card">Karta</option></select></label></div><label>Izoh<textarea v-model="payForm.note" maxlength="250" rows="2" placeholder="Avans, bonus yoki boshqa izoh"/></label>
    <p class="alert">Bir xodimga bir oy uchun faqat bitta oylik to‘lovi yoziladi. To‘lov xarajatlarda ham aks etadi.</p><p v-if="formError" class="alert error">{{ formError }}</p><button class="button primary full" :disabled="busy">{{ busy?'Saqlanmoqda…':'Oylikni to‘langan deb belgilash' }}</button>
  </form></AppModal>

  <AppModal :open="historyOpen" :title="`${selected?.name||''} · to‘lovlar tarixi`" @close="historyOpen=false"><div class="salary-history"><div v-for="item in payments" :key="item.id"><span><strong>{{ item.period }}</strong><small>{{ item.paid_on }} · {{ item.payment_method==='cash'?'Naqd':'Karta' }} · {{ item.actor_name }}</small></span><strong>{{ money(item.amount) }} so‘m</strong><p v-if="item.note">{{ item.note }}</p></div><div v-if="!payments.length" class="empty-state compact"><Banknote :size="32"/><p>Hali oylik to‘lovi kiritilmagan.</p></div></div></AppModal>
</template>
