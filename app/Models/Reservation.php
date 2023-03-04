<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasOne;

class Reservation extends Model
{
    use HasFactory;

    protected $table = 'reservation';

    protected $casts = [
        'cancellation' => "boolean",
        'chairs' => "array"
    ];

    /**
     * Get the buys for the blog post.
     */
    public function buys(): HasOne
    {
        return $this->hasOne(Buy::class);
    }

}
