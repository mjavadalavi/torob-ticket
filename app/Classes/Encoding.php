<?php

namespace App\Classes;

class Encoding
{
    static function base64url_encode($plainText)
    {
        return strtr(base64_encode($plainText), '+/=', '-_,');
    }

    static function base64url_decode($b64Text)
    {
        return base64_decode(strtr($b64Text, '-_,','+/='));
    }
}
