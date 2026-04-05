function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function marcarSubsidiado(campistaId) {
    if (!confirm('¿Estás seguro de marcar este campista como subsidiado?')) {
        return;
    }

    const csrftoken = getCookie('csrftoken');
    const url = `/subsidiado/${campistaId}/`;

    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken,
        },
        body: JSON.stringify({}),
    })
    .then(response => response.json())
    .then(data => {
        if (data.ok) {
            if (data.ya_marcado) {
                alert('El campista ya estaba marcado como subsidiado.');
            } else {
                alert('Campista marcado como subsidiado.');
            }
            location.reload();
        } else {
            alert('No se pudo marcar como subsidiado: ' + (data.error || 'Error desconocido'));
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error al marcar como subsidiado.');
    });
}