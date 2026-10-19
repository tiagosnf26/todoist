'use strict';
document.querySelectorAll('form[data-confirm]').forEach(form=>form.addEventListener('submit',ev=>{if(!window.confirm(form.dataset.confirm))ev.preventDefault();}));
const menu=document.getElementById('menu-botao');
if(menu)menu.addEventListener('click',()=>{const aberto=document.body.classList.toggle('menu-aberto');menu.setAttribute('aria-expanded',String(aberto));});
document.addEventListener('keydown',ev=>{if(ev.key==='Escape'){document.body.classList.remove('menu-aberto');if(menu)menu.setAttribute('aria-expanded','false');}});

const fechar=document.getElementById('menu-fechar');if(fechar)fechar.addEventListener('click',()=>{document.body.classList.remove('menu-aberto');if(menu)menu.setAttribute('aria-expanded','false');});

const filtrosTarefas=document.getElementById('filtros-tarefas');
if(filtrosTarefas) filtrosTarefas.querySelectorAll('select').forEach(select=>select.addEventListener('change',()=>filtrosTarefas.requestSubmit()));
