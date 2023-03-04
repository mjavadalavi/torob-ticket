<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasOne;

class Chairs extends Model
{
    use HasFactory;

    protected $table = 'bus_empty_chairs';
    protected $casts = [
        'chairs' => "array",
    ];


}
