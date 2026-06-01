
function toggleSort(){
    var input = document.getElementById('sort-input');
    var current = (input && input.value) ? input.value.toLowerCase() : 'desc';
    var next = current === 'asc' ? 'desc' : 'asc';
    if(input) input.value = next;
    var form = document.getElementById('filter-form');
    if(form){
        // resetear pagina si existe
        var pageInput = form.querySelector('input[name="page"]');
        if(pageInput) pageInput.value = 1;
        form.submit();
    } else {
        var params = new URLSearchParams(window.location.search);
        params.set('sort', next);
        params.set('page', 1);
        window.location.search = params.toString();
    }
}