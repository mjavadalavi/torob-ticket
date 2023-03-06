<?php

namespace App\Http\Controllers\API;

use App\Classes\Encoding;
use App\Enums\ReservationStatus;
use App\Enums\Status;
use App\Enums\StatusCode;
use App\Http\Controllers\Controller;
use App\Http\Requests\CancelReserveRequest;
use App\Http\Requests\StoreReserveRequest;
use App\Models\Reservation;
use Illuminate\Http\JsonResponse;
use Symfony\Component\HttpFoundation\Response;

class ReserveController extends Controller
{
    /**
     * @OA\Post(
     *      path="/reserve",
     *      operationId="storeReserveRequest",
     *      tags={"Reserve"},
     *      summary="Store new Reserve",
     *      description="Returns json of result storing data",
     *      @OA\Parameter(
     *           description="a hash id of searched by user",
     *           in="path",
     *           name="search_hash",
     *           required=true,
     *           @OA\Schema(type="string"),
     *       ),
     *      @OA\Parameter(
     *           description="count of passengers",
     *           in="path",
     *           name="passenger_count",
     *           required=true,
     *           @OA\Schema(type="string"),
     *
     *       ),
     *      @OA\Parameter(
     *           description="an aaray of chairs user needed .",
     *           in="path",
     *           name="chairs",
     *           required=true,
     *           @OA\Schema(type="string"),
     *           @OA\Items(
     *               type="array",
     *               @OA\Items()
     *           ),
     *       ),
     *      @OA\Response(
     *          response=201,
     *          description="Successful operation",
     *          content={
     *             @OA\MediaType(
     *                 mediaType="application/json",
     *                 @OA\Schema(
     *                     example={
     *                          "id":1,
     *                          "ws_id":3,
     *                          "chair_id": 2,
     *                          "passenger_count": 20,
     *                          "chairs": "[1,2,3,4]",
     *                          "status":1
     *                     }
     *                 )
     *             )
     *         }
     *       ),
     *      @OA\Response(
     *          response=400,
     *          description="Bad Request",
     *          content={
     *             @OA\MediaType(
     *                 mediaType="application/json",
     *                 @OA\Schema(
     *                     example={
     *                          "status":"HTTP Bad Request",
     *                          "code":"400",
     *                          "data":null
     *                     }
     *                 )
     *             )
     *         }
     *      )
     * )
     */

    public function store(StoreReserveRequest $request): JsonResponse
    {
        if ($request->validated()){

            $search_id = explode('|',Encoding::base64url_decode($request->input("search_hash")));
            $passenger_count = $request->input("passenger_count");
            $chairs = $request->input("chairs");

            $reserve = new Reservation();
            $reserve->ws_id = $search_id[0];
            $reserve->chair_id = $search_id[1];
            $reserve->passenger_count = $passenger_count;
            $reserve->chairs = $chairs;
            $reserve->save();
            return response()->json(['status' => Status::Success , "code" => StatusCode::Success, "data"=> $reserve])
                ->setStatusCode(Response::HTTP_ACCEPTED)
                ->header('Content-Type', 'application/json');
        }else{
            return response() ->json(['status' => Status::HTTP_BAD_REQUEST , "code" => StatusCode::Success, "data"=> null])
                ->setStatusCode(Response::HTTP_BAD_REQUEST)
                ->header('Content-Type', 'application/json');
        }
    }

    /**
     * @OA\Post(
     *      path="/Cancellation",
     *      operationId="CancelReserveRequest",
     *      tags={"Reserve"},
     *      summary="Cancel a Reserve",
     *      description="Returns json of result cancelling.",
     *      @OA\Parameter(
     *           description="an id of users reserved.",
     *           in="path",
     *           name="reserve_id",
     *           required=true,
     *           @OA\Schema(type="integer"),
     *       ),
     *      @OA\Response(
     *          response=201,
     *          description="Successful operation",
     *          content={
     *             @OA\MediaType(
     *                 mediaType="application/json",
     *                 @OA\Schema(
     *                     example={
     *                          "status":"Success",
     *                          "code":"1",
     *                          "data":"your reservations successfully cancelled"
     *                     }
     *                 )
     *             )
     *         }
     *       ),
     *      @OA\Response(
     *          response=404,
     *          description="Not Found",
     *          content={
     *             @OA\MediaType(
     *                 mediaType="application/json",
     *                 @OA\Schema(
     *                     example={
     *                          "status":"Failed",
     *                          "code":"-1",
     *                          "data":null
     *                     }
     *                 )
     *             )
     *         }
     *      ),
     *      @OA\Response(
     *          response=400,
     *          description="Bad Request",
     *          content={
     *             @OA\MediaType(
     *                 mediaType="application/json",
     *                 @OA\Schema(
     *                     example={
     *                          "status":"HTTP Bad Request",
     *                          "code":"400",
     *                          "data":null
     *                     }
     *                 )
     *             )
     *         }
     *      )
     * )
     */
    public function cancellation(CancelReserveRequest $request):JsonResponse
    {
        if ($request->validated()){
            $reserve = Reservation::find($request->input("reserve_id"));
            if (count($reserve) > 0){
                $reserve->status = ReservationStatus::Cancel;
                $reserve->chairs()->chairs[] = $request->chairs;
                $reserve->save();
                $response = ['status' => Status::Success , "code" => StatusCode::Success, "data"=> "your reservations successfully cancelled"];
                $response_code = Response::HTTP_OK;
            }else{
                $response = ['status' => Status::Failed , "code" => StatusCode::Failed, "data"=>null];
                $response_code = Response::HTTP_NOT_FOUND;
            }
        }else{
            $response = ['status' => Status::HTTP_BAD_REQUEST , "code" => StatusCode::Failed, "data"=> null];
            $response_code = Response::HTTP_BAD_REQUEST;
        }
        return  response() ->json($response)
            ->setStatusCode($response_code)
            ->header('Content-Type', 'application/json');
    }
}
