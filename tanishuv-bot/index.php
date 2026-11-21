<?php
// Bu papka ichidagi fayllar tashqaridan ochilmasligi kerak. Ochiq qism: public/
http_response_code(403);
header('Content-Type: text/plain; charset=utf-8');
echo "403";
